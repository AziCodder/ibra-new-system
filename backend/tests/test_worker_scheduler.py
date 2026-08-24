"""Воркер: расписание задач и правило «работает только главный узел»."""

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.core.database import async_session_factory
from app.workers import scheduler


def _jobs(**overrides) -> set[str]:
    return {job.id for job in scheduler.build_scheduler().get_jobs()}


@pytest.mark.asyncio
async def test_scheduler_registers_every_job(monkeypatch):
    monkeypatch.setattr(settings, "peer_url", "http://10.8.0.2/api/cluster/ping")
    monkeypatch.setattr(settings, "sync_replication", True)
    assert _jobs() == {
        "hourly_backup",
        "daily_backup",
        "backup_cleanup",
        "backup_verify",
        "storage_sync",
        "peer_watch",
        "replication_guard",
    }


@pytest.mark.asyncio
async def test_backup_jobs_disappear_when_backups_are_off(monkeypatch):
    monkeypatch.setattr(settings, "backup_enabled", False)
    monkeypatch.setattr(settings, "peer_url", "")
    monkeypatch.setattr(settings, "sync_replication", False)
    assert _jobs() == {"storage_sync"}  # сверка хранилища от бэкапов не зависит


@pytest.mark.asyncio
async def test_cluster_guards_appear_only_with_a_peer(monkeypatch):
    """Без адреса соседа следить не за кем — задача только мусорила бы в логах."""
    monkeypatch.setattr(settings, "peer_url", "")
    assert "peer_watch" not in _jobs()

    monkeypatch.setattr(settings, "peer_url", "http://10.8.0.1/api/cluster/ping")
    assert "peer_watch" in _jobs()


@pytest.mark.asyncio
async def test_primary_node_is_detected_from_the_database():
    """Тестовая база — не реплика, значит узел главный."""
    async with async_session_factory() as session:
        in_recovery = (await session.execute(text("SELECT pg_is_in_recovery()"))).scalar()
    assert in_recovery is False
    assert await scheduler.is_primary() is True


@pytest.mark.asyncio
async def test_standby_node_skips_the_job(monkeypatch):
    """На резерве задача не должна выполняться — иначе два бэкапа разом."""
    calls = []

    async def _job():
        calls.append(1)
        return "готово"

    monkeypatch.setattr(scheduler, "is_primary", lambda: _false())

    async def _false():
        return False

    await scheduler.only_on_primary("test", _job)()
    assert calls == []


@pytest.mark.asyncio
async def test_job_failure_does_not_kill_the_schedule(monkeypatch):
    """Сбой одной задачи не должен ронять воркер целиком."""

    async def _true():
        return True

    monkeypatch.setattr(scheduler, "is_primary", lambda: _true())

    async def _broken():
        raise RuntimeError("бэкап не задался")

    await scheduler.only_on_primary("test", _broken)()  # не должно поднять исключение
