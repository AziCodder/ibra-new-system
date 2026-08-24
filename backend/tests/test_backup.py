"""Бэкапы: снятие, отправка в два S3, срок хранения, проверка восстановлением.

``pg_dump`` и остальные утилиты подменены — проверяется логика сервиса, а не
работа postgres. Реальный дамп снимается в ручном прогоне (см. отчёт).
"""

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.database import async_session_factory, engine
from app.models.backup_run import BackupKind, BackupRun, BackupStatus
from app.models.stored_file import ReplicaState
from app.services import backup
from tests.test_replicated_storage import FakeBucket

DUMP_BYTES = b"PGDMP fake dump payload"


@pytest_asyncio.fixture
async def clean_runs():
    async with async_session_factory() as session:
        await session.execute(delete(BackupRun))
        await session.commit()
    await engine.dispose()


@pytest.fixture
def fake_dump(monkeypatch, tmp_path):
    """pg_dump подменён: пишет заглушку в тот же файл, что и настоящий."""
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path))

    async def _dump(target):
        target.write_bytes(DUMP_BYTES)

    monkeypatch.setattr(backup, "_dump", _dump)
    return tmp_path


@pytest.fixture
def buckets(monkeypatch):
    primary, mirror = FakeBucket("primary"), FakeBucket("mirror")
    monkeypatch.setattr(backup, "backup_targets", lambda: [("primary", primary), ("mirror", mirror)])
    monkeypatch.setattr(backup, "backup_buckets", lambda: [primary, mirror])
    return primary, mirror


async def _run(run_id: int) -> BackupRun:
    async with async_session_factory() as session:
        return await session.get(BackupRun, run_id)


@pytest.mark.asyncio
async def test_backup_lands_in_both_buckets(clean_runs, fake_dump, buckets):
    primary, mirror = buckets

    result = await backup.create(BackupKind.hourly)
    assert result["status"] == "ok"
    assert result["object_key"].startswith("hourly/")

    assert primary.objects[result["object_key"]][0] == DUMP_BYTES
    assert mirror.objects[result["object_key"]][0] == DUMP_BYTES

    run = await _run(result["id"])
    assert run.status == BackupStatus.ok
    assert run.primary_state == ReplicaState.ok
    assert run.mirror_state == ReplicaState.ok
    assert run.size == len(DUMP_BYTES)
    assert run.sha256 == result["sha256"]
    assert run.local_path == ""  # локальный файл убран после отправки


@pytest.mark.asyncio
async def test_local_copy_survives_when_upload_fails(clean_runs, fake_dump, buckets):
    """Если S3 недоступен, копию нельзя выбрасывать — она единственная."""
    primary, mirror = buckets
    primary.fail = mirror.fail = True

    result = await backup.create(BackupKind.hourly)
    run = await _run(result["id"])

    assert run.status == BackupStatus.ok
    assert run.primary_state == ReplicaState.error
    assert run.local_path and (fake_dump / "hourly").exists()
    assert "недоступен" in run.error


@pytest.mark.asyncio
async def test_failed_dump_is_recorded_not_swallowed(clean_runs, fake_dump, buckets, monkeypatch):
    async def _boom(target):
        raise backup.BackupError("pg_dump: connection refused")

    monkeypatch.setattr(backup, "_dump", _boom)

    result = await backup.create(BackupKind.daily)
    assert result["status"] == "failed"

    run = await _run(result["id"])
    assert run.status == BackupStatus.failed
    assert "connection refused" in run.error


@pytest.mark.asyncio
async def test_cleanup_removes_only_expired_hourly(clean_runs, fake_dump, buckets, monkeypatch):
    """Часовые старше срока — удалить; свежие часовые и суточные — не трогать."""
    from datetime import UTC, datetime, timedelta

    primary, mirror = buckets
    old = await backup.create(BackupKind.hourly)
    fresh = await backup.create(BackupKind.hourly)
    permanent = await backup.create(BackupKind.daily)

    async with async_session_factory() as session:
        row = await session.get(BackupRun, old["id"])
        row.started_at = datetime.now(UTC) - timedelta(days=30)
        stale_daily = await session.get(BackupRun, permanent["id"])
        stale_daily.started_at = datetime.now(UTC) - timedelta(days=365)
        await session.commit()
    await engine.dispose()

    report = await backup.cleanup()
    assert report["removed"] == 1 and report["failed"] == 0

    assert old["object_key"] not in primary.objects
    assert old["object_key"] not in mirror.objects
    assert fresh["object_key"] in primary.objects
    # Суточная копия годичной давности обязана уцелеть.
    assert permanent["object_key"] in primary.objects

    assert (await _run(old["id"])).deleted_at is not None
    assert (await _run(permanent["id"])).deleted_at is None


@pytest.mark.asyncio
async def test_cleanup_keeps_the_row_when_bucket_refuses(clean_runs, fake_dump, buckets):
    """Не удалось стереть объект — не помечать копию удалённой."""
    from datetime import UTC, datetime, timedelta

    primary, mirror = buckets
    old = await backup.create(BackupKind.hourly)
    async with async_session_factory() as session:
        row = await session.get(BackupRun, old["id"])
        row.started_at = datetime.now(UTC) - timedelta(days=30)
        await session.commit()
    await engine.dispose()

    primary.fail = True
    report = await backup.cleanup()

    assert report["removed"] == 0 and report["failed"] == 1
    assert (await _run(old["id"])).deleted_at is None


@pytest.mark.asyncio
async def test_verify_reports_ok_when_restore_succeeds(clean_runs, fake_dump, buckets, monkeypatch):
    created = await backup.create(BackupKind.daily)

    async def _restore(conn, scratch, dump_path):
        assert dump_path.read_bytes() == DUMP_BYTES
        return "восстановлено — users: 3, orders: 12, clients: 4"

    monkeypatch.setattr(backup, "_restore_and_count", _restore)

    result = await backup.verify_last(BackupKind.daily)
    assert result["status"] == "ok"

    run = await _run(created["id"])
    assert run.verify_status == BackupStatus.ok
    assert "orders: 12" in run.verify_detail


@pytest.mark.asyncio
async def test_verify_marks_a_broken_backup(clean_runs, fake_dump, buckets, monkeypatch):
    created = await backup.create(BackupKind.daily)

    async def _restore(conn, scratch, dump_path):
        raise backup.BackupError("восстановленная база пуста: users: 0")

    monkeypatch.setattr(backup, "_restore_and_count", _restore)

    result = await backup.verify_last(BackupKind.daily)
    assert result["status"] == "failed"

    run = await _run(created["id"])
    assert run.verify_status == BackupStatus.failed
    assert "пуста" in run.verify_detail


@pytest.mark.asyncio
async def test_summary_shows_latest_of_each_kind(clean_runs, fake_dump, buckets):
    await backup.create(BackupKind.hourly)
    daily = await backup.create(BackupKind.daily)

    report = await backup.summary()
    assert report["enabled"] is True
    assert report["retention_days"] == settings.backup_hourly_retention_days
    assert report["hourly"] is not None
    assert report["daily"]["object_key"] == daily["object_key"]
    assert report["daily"]["copies"] == 2


@pytest.mark.asyncio
async def test_history_is_newest_first(clean_runs, fake_dump, buckets):
    first = await backup.create(BackupKind.hourly)
    second = await backup.create(BackupKind.daily)

    rows = await backup.history(limit=10)
    assert [row.id for row in rows][:2] == [second["id"], first["id"]]


@pytest.mark.asyncio
async def test_disabled_backups_do_nothing(clean_runs, fake_dump, buckets, monkeypatch):
    monkeypatch.setattr(settings, "backup_enabled", False)
    assert await backup.create(BackupKind.hourly) == {"enabled": False}

    async with async_session_factory() as session:
        assert (await session.execute(select(BackupRun))).first() is None
