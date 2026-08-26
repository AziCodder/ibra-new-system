"""Клиент к S3-совместимым хранилищам (HostKey S3 — основное, Backblaze B2 — зеркало).

Тонкая обёртка над boto3: сам boto3 синхронный, поэтому каждый вызов уходит в
пул потоков (``asyncio.to_thread``) — событийный цикл FastAPI не блокируется.

Контрольная сумма файла кладётся в метаданные объекта (``x-amz-meta-sha256``).
Сверять бакеты по ETag нельзя: при multipart-загрузке и у части провайдеров ETag — не MD5
содержимого, а собственный идентификатор провайдера. Своя SHA-256 в метаданных
позволяет сравнивать бакеты одним HEAD-запросом, не скачивая файл.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

SHA_META_KEY = "sha256"
_NOT_FOUND_CODES = {"404", "NoSuchKey", "NotFound"}


class S3Error(Exception):
    """Ошибка обращения к бакету (сеть, доступ, отсутствующий объект)."""


@dataclass(frozen=True)
class S3Config:
    """Реквизиты одного бакета. ``name`` — машинный ключ (primary/mirror),
    ``label`` — человекочитаемое имя для админки."""

    name: str
    label: str
    endpoint_url: str
    region: str
    access_key: str
    secret_key: str
    bucket: str
    prefix: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.endpoint_url and self.bucket and self.access_key and self.secret_key)


@dataclass(frozen=True)
class ObjectInfo:
    """Что известно об объекте без скачивания: размер и наша SHA-256."""

    key: str
    size: int
    sha256: str | None


def _is_not_found(exc: Exception) -> bool:
    if isinstance(exc, ClientError):
        error = exc.response.get("Error", {})
        return str(error.get("Code")) in _NOT_FOUND_CODES
    return False


class S3Bucket:
    """Один бакет. Клиент boto3 создаётся лениво и переиспользуется."""

    def __init__(self, config: S3Config, *, timeout: float = 15.0) -> None:
        self.config = config
        self._timeout = timeout
        self._client = None
        self._lock = threading.Lock()

    # ────────────────────────────────────────────────────────────── внутреннее

    def _get_client(self):
        if self._client is None:
            with self._lock:
                if self._client is None:
                    self._client = boto3.client(
                        "s3",
                        endpoint_url=self.config.endpoint_url,
                        region_name=self.config.region or None,
                        aws_access_key_id=self.config.access_key,
                        aws_secret_access_key=self.config.secret_key,
                        config=BotoConfig(
                            signature_version="s3v4",
                            # Path-style: у S3-совместимых провайдеров
                            # virtual-host адресация часто не работает.
                            s3={"addressing_style": "path"},
                            retries={"max_attempts": 3, "mode": "standard"},
                            connect_timeout=self._timeout,
                            read_timeout=self._timeout,
                        ),
                    )
        return self._client

    def _full_key(self, key: str) -> str:
        return f"{self.config.prefix}{key}" if self.config.prefix else key

    def _strip_prefix(self, full_key: str) -> str:
        prefix = self.config.prefix
        return full_key[len(prefix):] if prefix and full_key.startswith(prefix) else full_key

    # ─────────────────────────────────────────────────────────── синхронные io

    def _put_sync(self, key: str, data: bytes, sha256: str, content_type: str | None) -> None:
        extra = {"Metadata": {SHA_META_KEY: sha256}}
        if content_type:
            extra["ContentType"] = content_type
        self._get_client().put_object(
            Bucket=self.config.bucket, Key=self._full_key(key), Body=data, **extra
        )

    def _get_sync(self, key: str) -> bytes:
        response = self._get_client().get_object(Bucket=self.config.bucket, Key=self._full_key(key))
        return response["Body"].read()

    def _delete_sync(self, key: str) -> None:
        self._get_client().delete_object(Bucket=self.config.bucket, Key=self._full_key(key))

    def _head_sync(self, key: str) -> ObjectInfo | None:
        try:
            response = self._get_client().head_object(
                Bucket=self.config.bucket, Key=self._full_key(key)
            )
        except ClientError as exc:
            if _is_not_found(exc):
                return None
            raise
        metadata = response.get("Metadata") or {}
        return ObjectInfo(
            key=key,
            size=int(response.get("ContentLength") or 0),
            sha256=metadata.get(SHA_META_KEY),
        )

    def _list_sync(self, limit: int | None) -> dict[str, ObjectInfo]:
        client = self._get_client()
        paginator = client.get_paginator("list_objects_v2")
        found: dict[str, ObjectInfo] = {}
        for page in paginator.paginate(
            Bucket=self.config.bucket, Prefix=self.config.prefix or ""
        ):
            for item in page.get("Contents", []):
                key = self._strip_prefix(item["Key"])
                # SHA-256 живёт в метаданных, а листинг их не отдаёт: здесь
                # только факт наличия и размер, сверка хешей — точечным HEAD.
                found[key] = ObjectInfo(key=key, size=int(item.get("Size") or 0), sha256=None)
                if limit is not None and len(found) >= limit:
                    return found
        return found

    def _ping_sync(self) -> None:
        self._get_client().head_bucket(Bucket=self.config.bucket)

    # ─────────────────────────────────────────────────────────────── публичное

    async def put(self, key: str, data: bytes, *, sha256: str, content_type: str | None = None) -> None:
        await self._run(self._put_sync, key, data, sha256, content_type)

    async def get(self, key: str) -> bytes:
        return await self._run(self._get_sync, key)

    async def delete(self, key: str) -> None:
        await self._run(self._delete_sync, key)

    async def head(self, key: str) -> ObjectInfo | None:
        return await self._run(self._head_sync, key)

    async def list_keys(self, limit: int | None = None) -> dict[str, ObjectInfo]:
        return await self._run(self._list_sync, limit)

    async def ping(self) -> None:
        await self._run(self._ping_sync)

    async def _run(self, func, *args):
        try:
            return await asyncio.to_thread(func, *args)
        except (ClientError, BotoCoreError) as exc:
            if _is_not_found(exc):
                raise S3Error(f"{self.config.label}: объект не найден") from exc
            raise S3Error(f"{self.config.label}: {exc}") from exc

    def __repr__(self) -> str:  # pragma: no cover — только для логов
        return f"S3Bucket({self.config.name}:{self.config.bucket})"
