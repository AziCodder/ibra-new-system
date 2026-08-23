"""Сверка и починка двух бакетов: расхождения находятся и лечатся."""

import pytest
import pytest_asyncio
from sqlalchemy import delete

from app.core.database import async_session_factory, engine
from app.models.stored_file import ReplicaState, StoredFile
from app.services import file_registry, storage_sync
from app.services import storage as storage_module
from app.services.storage import ReplicatedS3Storage
from tests.test_replicated_storage import FakeBucket


@pytest_asyncio.fixture
async def store(monkeypatch):
    """Активное хранилище — пара бакетов в памяти.

    Реестр перед каждым тестом пуст: сверка и починка ходят по всему
    реестру, поэтому чужие строки ломали бы счётчики в отчётах.
    """
    async with async_session_factory() as session:
        await session.execute(delete(StoredFile))
        await session.commit()
    # Фикстура и сам тест живут в разных циклах событий: соединение из
    # пула, открытое здесь, в тесте уже нельзя переиспользовать.
    await engine.dispose()

    primary, mirror = FakeBucket("primary"), FakeBucket("mirror")
    replicated = ReplicatedS3Storage(primary, mirror)
    monkeypatch.setattr(storage_module, "storage", replicated)
    return replicated


async def _cleanup(*keys: str) -> None:
    async with async_session_factory() as session:
        for key in keys:
            row = await session.get(StoredFile, key)
            if row is not None:
                await session.delete(row)
        await session.commit()


@pytest.mark.asyncio
async def test_verify_notices_object_vanished_from_mirror(store):
    key = await store.save("doc.txt", b"payload")
    try:
        store.mirror.objects.pop(key)  # объект пропал мимо приложения

        report = await storage_sync.verify()
        assert report["enabled"] and report["mismatched"] >= 1

        row = await file_registry.get(key)
        assert row.mirror_state == ReplicaState.missing
        assert row.checked_at is not None
    finally:
        await _cleanup(key)


@pytest.mark.asyncio
async def test_verify_notices_wrong_size(store):
    key = await store.save("doc.txt", b"payload")
    try:
        store.mirror.objects[key] = (b"tampered payload", store.mirror.objects[key][1])

        await storage_sync.verify()
        row = await file_registry.get(key)
        assert row.mirror_state == ReplicaState.error
    finally:
        await _cleanup(key)


@pytest.mark.asyncio
async def test_repair_refills_the_lagging_mirror(store):
    store.mirror.fail = True
    key = await store.save("doc.txt", b"payload")  # зеркало отстало при загрузке
    try:
        store.mirror.fail = False

        report = await storage_sync.repair()
        assert report["repaired"] == 1
        assert store.mirror.objects[key][0] == b"payload"

        row = await file_registry.get(key)
        assert row.in_sync
    finally:
        await _cleanup(key)


@pytest.mark.asyncio
async def test_repair_refuses_a_corrupted_source(store):
    """Копия с чужим хешем не может быть образцом — иначе порча размножится."""
    store.mirror.fail = True
    key = await store.save("doc.txt", b"payload")
    try:
        store.mirror.fail = False
        store.primary.objects[key] = (b"corrupted", store.primary.objects[key][1])
        await file_registry.mark_state(key, primary_state=ReplicaState.ok)

        report = await storage_sync.repair()
        assert report["repaired"] == 0
        assert report["lost"] == 1
        assert key not in store.mirror.objects

        row = await file_registry.get(key)
        assert "нет исправной копии" in row.last_error
    finally:
        await _cleanup(key)


@pytest.mark.asyncio
async def test_purge_tombstones_finishes_a_half_done_delete(store):
    key = await store.save("doc.txt", b"payload")
    store.mirror.fail = True
    await store.delete(key)  # зеркало не подтвердило удаление
    try:
        store.mirror.fail = False

        report = await storage_sync.purge_tombstones()
        assert report["purged"] == 1
        assert key not in store.mirror.objects
        assert await file_registry.get(key) is None
    finally:
        await _cleanup(key)


@pytest.mark.asyncio
async def test_scan_orphans_reports_unregistered_objects(store):
    await store.primary.put("stray.pdf", b"bytes", sha256="deadbeef")

    report = await storage_sync.scan_orphans()
    assert report["orphans"] == 1
    assert report["sample"] == ["stray.pdf"]


@pytest.mark.asyncio
async def test_sync_is_inert_on_local_storage(monkeypatch):
    """На локальном хранилище сверять нечего — задачи должны молчать."""
    from app.services.storage import LocalStorage

    monkeypatch.setattr(storage_module, "storage", LocalStorage("/tmp/uploads"))
    assert (await storage_sync.verify())["enabled"] is False
    assert (await storage_sync.repair())["enabled"] is False
    assert (await storage_sync.purge_tombstones())["enabled"] is False
    assert await storage_sync.ping_buckets() == []
