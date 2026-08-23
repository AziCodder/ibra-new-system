"""Двойная запись файлов в два S3: что происходит, когда один из них падает.

Бакеты подменены на память — тесты проверяют поведение хранилища, а не сеть.
"""

import hashlib

import pytest

from app.core.database import async_session_factory
from app.models.stored_file import ReplicaState, StoredFile
from app.services import file_registry
from app.services.s3 import ObjectInfo, S3Error
from app.services.storage import ReplicatedS3Storage, StorageError


class FakeBucket:
    """Бакет в памяти. ``fail`` включает имитацию недоступного хранилища."""

    def __init__(self, name: str = "fake") -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.fail = False

        class _Config:
            pass

        self.config = _Config()
        self.config.name = name
        self.config.label = name

    def _guard(self) -> None:
        if self.fail:
            raise S3Error(f"{self.config.label}: недоступен")

    async def put(self, key, data, *, sha256, content_type=None):
        self._guard()
        self.objects[key] = (data, sha256)

    async def get(self, key):
        self._guard()
        if key not in self.objects:
            raise S3Error("объект не найден")
        return self.objects[key][0]

    async def delete(self, key):
        self._guard()
        self.objects.pop(key, None)

    async def head(self, key):
        self._guard()
        if key not in self.objects:
            return None
        data, sha = self.objects[key]
        return ObjectInfo(key=key, size=len(data), sha256=sha)


async def _cleanup(key: str) -> None:
    async with async_session_factory() as session:
        row = await session.get(StoredFile, key)
        if row is not None:
            await session.delete(row)
            await session.commit()


@pytest.mark.asyncio
async def test_saves_to_both_buckets():
    primary, mirror = FakeBucket("primary"), FakeBucket("mirror")
    store = ReplicatedS3Storage(primary, mirror)

    key = await store.save("contract.pdf", b"hello world")
    try:
        assert primary.objects[key][0] == b"hello world"
        assert mirror.objects[key][0] == b"hello world"
        assert primary.objects[key][1] == hashlib.sha256(b"hello world").hexdigest()

        row = await file_registry.get(key)
        assert row is not None
        assert row.primary_state == ReplicaState.ok
        assert row.mirror_state == ReplicaState.ok
        assert row.in_sync
        assert row.replicated_at is not None
    finally:
        await _cleanup(key)


@pytest.mark.asyncio
async def test_mirror_failure_does_not_break_upload():
    """Зеркало лежит — пользователь всё равно должен суметь загрузить файл."""
    primary, mirror = FakeBucket("primary"), FakeBucket("mirror")
    mirror.fail = True
    store = ReplicatedS3Storage(primary, mirror)

    key = await store.save("photo.jpg", b"image bytes")
    try:
        assert primary.objects[key][0] == b"image bytes"
        row = await file_registry.get(key)
        assert row.primary_state == ReplicaState.ok
        assert row.mirror_state == ReplicaState.error
        assert not row.in_sync  # попадёт в дозаливку
        assert "недоступен" in row.last_error
    finally:
        await _cleanup(key)


@pytest.mark.asyncio
async def test_primary_failure_rejects_upload():
    """Основной бакет не принял файл — принимать загрузку нельзя."""
    primary, mirror = FakeBucket("primary"), FakeBucket("mirror")
    primary.fail = True
    store = ReplicatedS3Storage(primary, mirror)

    with pytest.raises(StorageError):
        await store.save("contract.pdf", b"data")

    assert mirror.objects == {}


@pytest.mark.asyncio
async def test_read_falls_back_to_mirror():
    primary, mirror = FakeBucket("primary"), FakeBucket("mirror")
    store = ReplicatedS3Storage(primary, mirror)
    key = await store.save("contract.pdf", b"payload")
    try:
        primary.fail = True
        assert await store.get(key) == b"payload"

        row = await file_registry.get(key)
        assert row.primary_state == ReplicaState.missing  # починка подхватит
    finally:
        await _cleanup(key)


@pytest.mark.asyncio
async def test_read_fails_when_both_down():
    primary, mirror = FakeBucket("primary"), FakeBucket("mirror")
    store = ReplicatedS3Storage(primary, mirror)
    key = await store.save("contract.pdf", b"payload")
    try:
        primary.fail = mirror.fail = True
        with pytest.raises(StorageError):
            await store.get(key)
    finally:
        await _cleanup(key)


@pytest.mark.asyncio
async def test_delete_removes_from_both_and_clears_registry():
    primary, mirror = FakeBucket("primary"), FakeBucket("mirror")
    store = ReplicatedS3Storage(primary, mirror)
    key = await store.save("doc.txt", b"bytes")

    await store.delete(key)
    assert primary.objects == {}
    assert mirror.objects == {}
    assert await file_registry.get(key) is None


@pytest.mark.asyncio
async def test_delete_keeps_tombstone_when_mirror_is_down():
    """Удаление не подтверждено зеркалом — файл не должен «потеряться»
    из учёта, иначе копия останется лежать в зеркале навсегда."""
    primary, mirror = FakeBucket("primary"), FakeBucket("mirror")
    store = ReplicatedS3Storage(primary, mirror)
    key = await store.save("doc.txt", b"bytes")
    try:
        mirror.fail = True
        await store.delete(key)

        row = await file_registry.get(key)
        assert row is not None
        assert row.deleted_at is not None
        assert mirror.objects[key][0] == b"bytes"  # копия ещё жива
        assert [t.key for t in await file_registry.tombstones()] .count(key) == 1
    finally:
        await _cleanup(key)


@pytest.mark.asyncio
async def test_without_mirror_registry_marks_it_disabled():
    primary = FakeBucket("primary")
    store = ReplicatedS3Storage(primary, None)
    key = await store.save("doc.txt", b"bytes")
    try:
        row = await file_registry.get(key)
        assert row.mirror_state == ReplicaState.disabled
        assert row.in_sync  # одиночный бакет — не рассинхрон, а конфигурация
    finally:
        await _cleanup(key)


@pytest.mark.asyncio
async def test_pending_lists_lagging_files():
    primary, mirror = FakeBucket("primary"), FakeBucket("mirror")
    mirror.fail = True
    store = ReplicatedS3Storage(primary, mirror)
    key = await store.save("doc.txt", b"bytes")
    try:
        assert key in {row.key for row in await file_registry.pending()}
    finally:
        await _cleanup(key)


@pytest.mark.asyncio
async def test_validation_runs_before_any_write():
    primary, mirror = FakeBucket("primary"), FakeBucket("mirror")
    store = ReplicatedS3Storage(primary, mirror)

    with pytest.raises(StorageError):
        await store.save("script.exe", b"data")
    with pytest.raises(StorageError):
        await store.save("big.pdf", b"x" * (3 * 1024 * 1024 + 1), max_size=3 * 1024 * 1024)

    assert primary.objects == {}
    assert mirror.objects == {}
