"""Хранилище пользовательских вложений.

Два режима, выбираются настройкой ``STORAGE_BACKEND``:

* ``local`` — папка на диске (разработка и тесты);
* ``s3`` — два независимых S3 (HostKey — основной, Storj — зеркало).

В режиме ``s3`` каждая загрузка пишется в оба бакета. Основной обязателен:
если он не принял файл — загрузка честно падает, «приняли и потеряли» быть
не должно. Зеркало не обязательно: его недоступность не роняет работу
пользователя, файл помечается отставшим и дозаливается фоновой задачей.
Чтение идёт из основного, а при его сбое — из зеркала, поэтому авария
одного провайдера не закрывает доступ к вложениям.
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import settings
from app.models.stored_file import ReplicaState
from app.services import file_registry
from app.services.s3 import S3Bucket, S3Error

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB — default, used where ТЗ doesn't specify a context limit
# Per-context limits from ТЗ §6/§8: order attachments 3 MB, payment-request attachments 5 MB.
CONTEXT_MAX_SIZES = {
    "order": 3 * 1024 * 1024,
    "payment_request": 5 * 1024 * 1024,
}
ALLOWED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".txt", ".csv", ".zip", ".rar",
}


class StorageError(Exception):
    pass


def validate_upload(filename: str, data: bytes, max_size: int) -> str:
    """Проверить тип и размер, вернуть нормализованное расширение."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise StorageError(f"File type '{ext}' not allowed")
    if len(data) > max_size:
        raise StorageError(f"File exceeds {max_size // (1024 * 1024)}MB limit")
    return ext


class Storage(ABC):
    @abstractmethod
    async def save(self, filename: str, data: bytes, max_size: int = MAX_FILE_SIZE) -> str:
        ...

    @abstractmethod
    async def get(self, key: str) -> bytes:
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        ...


class LocalStorage(Storage):
    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or settings.upload_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _validate(self, filename: str, data: bytes, max_size: int) -> None:
        validate_upload(filename, data, max_size)

    async def save(self, filename: str, data: bytes, max_size: int = MAX_FILE_SIZE) -> str:
        ext = validate_upload(filename, data, max_size)
        key = f"{uuid.uuid4().hex}{ext}"
        filepath = self.base_dir / key
        filepath.write_bytes(data)
        return key

    async def get(self, key: str) -> bytes:
        filepath = self.base_dir / key
        if not filepath.exists():
            raise StorageError("File not found")
        safe = os.path.commonpath([self.base_dir.resolve(), filepath.resolve()])
        if safe != str(self.base_dir.resolve()):
            raise StorageError("Invalid file path")
        return filepath.read_bytes()

    async def delete(self, key: str) -> None:
        filepath = self.base_dir / key
        if not filepath.exists():
            return
        safe = os.path.commonpath([self.base_dir.resolve(), filepath.resolve()])
        if safe != str(self.base_dir.resolve()):
            raise StorageError("Invalid file path")
        filepath.unlink()


class ReplicatedS3Storage(Storage):
    """Два бакета: основной обязателен, зеркало — «по возможности»."""

    def __init__(self, primary: S3Bucket, mirror: S3Bucket | None = None) -> None:
        self.primary = primary
        self.mirror = mirror

    async def save(self, filename: str, data: bytes, max_size: int = MAX_FILE_SIZE) -> str:
        ext = validate_upload(filename, data, max_size)
        key = f"{uuid.uuid4().hex}{ext}"
        sha256 = hashlib.sha256(data).hexdigest()
        content_type = mimetypes.guess_type(filename)[0]

        try:
            await self.primary.put(key, data, sha256=sha256, content_type=content_type)
        except S3Error as exc:
            # Основное хранилище не приняло файл — принимать загрузку нельзя.
            await file_registry.record_saved(
                key,
                filename=filename,
                size=len(data),
                sha256=sha256,
                primary_state=ReplicaState.error,
                mirror_state=ReplicaState.pending,
                error=str(exc),
            )
            logger.error("s3 primary put failed for %s: %s", key, exc)
            raise StorageError("Storage unavailable, file was not saved") from exc

        mirror_state = ReplicaState.disabled
        error = ""
        if self.mirror is not None:
            try:
                await self.mirror.put(key, data, sha256=sha256, content_type=content_type)
                mirror_state = ReplicaState.ok
            except S3Error as exc:
                # Зеркало отстало — это не повод отказывать пользователю:
                # файл уже сохранён, дозальёт фоновая задача.
                mirror_state = ReplicaState.error
                error = str(exc)
                logger.warning("s3 mirror put failed for %s: %s", key, exc)

        await file_registry.record_saved(
            key,
            filename=filename,
            size=len(data),
            sha256=sha256,
            primary_state=ReplicaState.ok,
            mirror_state=mirror_state,
            error=error,
        )
        return key

    async def get(self, key: str) -> bytes:
        try:
            return await self.primary.get(key)
        except S3Error as primary_exc:
            if self.mirror is None:
                raise StorageError("File not found") from primary_exc
            logger.warning("s3 primary read failed for %s: %s — читаю зеркало", key, primary_exc)
            try:
                data = await self.mirror.get(key)
            except S3Error as mirror_exc:
                raise StorageError("File not found") from mirror_exc
            # Основной не отдал то, что обязан хранить: пометить, чтобы
            # фоновая починка вернула копию на место.
            await file_registry.mark_state(
                key, primary_state=ReplicaState.missing, error=str(primary_exc)
            )
            return data

    async def delete(self, key: str) -> None:
        primary_removed = await self._try_delete(self.primary, key)
        mirror_removed = True
        if self.mirror is not None:
            mirror_removed = await self._try_delete(self.mirror, key)
        await file_registry.mark_deleted(key, fully_removed=primary_removed and mirror_removed)

    @staticmethod
    async def _try_delete(bucket: S3Bucket, key: str) -> bool:
        try:
            await bucket.delete(key)
            return True
        except S3Error as exc:
            logger.warning("s3 delete failed in %s for %s: %s", bucket.config.name, key, exc)
            return False

    def buckets(self) -> list[S3Bucket]:
        return [b for b in (self.primary, self.mirror) if b is not None]


def build_storage() -> Storage:
    """Собрать хранилище по конфигурации."""
    if settings.storage_backend != "s3":
        return LocalStorage()

    primary = S3Bucket(settings.s3_primary_config)
    mirror_config = settings.s3_mirror_config
    if not mirror_config.configured:
        logger.warning(
            "S3 mirror is not configured — файлы хранятся в одном бакете, "
            "отказоустойчивость хранилища неполная"
        )
        return ReplicatedS3Storage(primary, None)
    return ReplicatedS3Storage(primary, S3Bucket(mirror_config))


storage: Storage = build_storage()
