"""Ручные копии: имя, удаление и откат на выбранную копию."""

import pytest
import pytest_asyncio
from sqlalchemy import delete

from app.core.config import settings
from app.core.database import async_session_factory, engine
from app.models.backup_run import BackupKind, BackupRun, BackupStatus
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


async def _row(run_id: int) -> BackupRun:
    async with async_session_factory() as session:
        return await session.get(BackupRun, run_id)


# ── имя копии ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Перед правками цен", "pered-pravkami-cen"),
        ("before  migration!!", "before-migration"),
        ("...", ""),
        ("", ""),
    ],
)
def test_label_becomes_a_readable_key(label, expected):
    """Имя пишут по-русски, а ключ в бакете должен оставаться читаемым."""
    assert backup._slugify(label) == expected


@pytest.mark.asyncio
async def test_manual_backup_keeps_its_name(clean_runs, fake_dump, buckets):
    result = await backup.create(BackupKind.manual, "Перед правками цен")
    run = await _row(result["id"])

    assert run.label == "Перед правками цен"
    assert run.title == "Перед правками цен"
    assert "pered-pravkami-cen" in run.object_key
    assert run.permanent is True  # ручная копия — постоянная


@pytest.mark.asyncio
async def test_manual_backups_survive_retention(clean_runs, fake_dump, buckets):
    """Чистка по сроку не должна трогать ручные копии, даже старые."""
    from datetime import UTC, datetime, timedelta

    primary, _ = buckets
    manual = await backup.create(BackupKind.manual, "Годовой архив")
    async with async_session_factory() as session:
        row = await session.get(BackupRun, manual["id"])
        row.started_at = datetime.now(UTC) - timedelta(days=400)
        await session.commit()
    await engine.dispose()

    report = await backup.cleanup()

    assert report["removed"] == 0
    assert manual["object_key"] in primary.objects
    assert (await _row(manual["id"])).deleted_at is None


# ── удаление ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_removes_the_copy_everywhere(clean_runs, fake_dump, buckets):
    primary, mirror = buckets
    created = await backup.create(BackupKind.manual, "Тестовая")

    result = await backup.remove(created["id"])

    assert result["status"] == "ok" and result["title"] == "Тестовая"
    assert created["object_key"] not in primary.objects
    assert created["object_key"] not in mirror.objects
    assert (await _row(created["id"])).deleted_at is not None
    assert created["id"] not in {run.id for run in await backup.history()}


@pytest.mark.asyncio
async def test_delete_does_not_lie_when_storage_refuses(clean_runs, fake_dump, buckets):
    """Бакет не подтвердил удаление — копия не может считаться удалённой."""
    primary, _ = buckets
    created = await backup.create(BackupKind.manual, "Тестовая")
    primary.fail = True

    result = await backup.remove(created["id"])

    assert result["status"] == "failed"
    assert (await _row(created["id"])).deleted_at is None


@pytest.mark.asyncio
async def test_delete_refuses_while_the_copy_is_being_made(clean_runs, fake_dump, buckets):
    async with async_session_factory() as session:
        run = BackupRun(kind=BackupKind.manual, status=BackupStatus.running, object_key="manual/x")
        session.add(run)
        await session.commit()
        run_id = run.id
    await engine.dispose()

    assert (await backup.remove(run_id))["status"] == "busy"


# ── откат ──────────────────────────────────────────────────────────────────


@pytest.fixture
def fake_swap(monkeypatch):
    """Подмена базы — единственное, что нельзя выполнить в тестах по-настоящему."""
    calls = []

    async def _swap(object_key, local_path):
        calls.append(object_key)
        return f"база восстановлена из {object_key}; прежняя сохранена как ibra_orders_before_restore_x"

    monkeypatch.setattr(backup, "_swap_in_backup", _swap)
    return calls


@pytest.mark.asyncio
async def test_restore_takes_a_safety_copy_first(clean_runs, fake_dump, buckets, fake_swap):
    """Откат без страховки — потеря текущих данных без права на ошибку."""
    target = await backup.create(BackupKind.manual, "Точка возврата")

    result = await backup.restore(target["id"])

    assert result["status"] == "ok"
    assert fake_swap == [target["object_key"]]

    safety = await _row(result["safety_id"])
    assert safety.kind == BackupKind.manual
    assert safety.label == "перед откатом: Точка возврата"

    run = await _row(target["id"])
    assert run.restore_status == BackupStatus.ok
    assert run.restored_at is not None
    assert "before_restore" in run.restore_detail


@pytest.mark.asyncio
async def test_restore_aborts_when_the_safety_copy_fails(clean_runs, fake_dump, buckets, fake_swap, monkeypatch):
    target = await backup.create(BackupKind.manual, "Точка возврата")

    async def _boom(path):
        raise backup.BackupError("pg_dump: диск переполнен")

    monkeypatch.setattr(backup, "_dump", _boom)

    result = await backup.restore(target["id"])

    assert result["status"] == "failed"
    assert fake_swap == []  # до подмены базы дело не дошло
    run = await _row(target["id"])
    # Попытка зафиксирована, но её итог — провал: «откат выполнен» не про неё.
    assert run.restore_status == BackupStatus.failed
    assert run.restored_at is not None


@pytest.mark.asyncio
async def test_restore_reports_a_broken_swap(clean_runs, fake_dump, buckets, monkeypatch):
    target = await backup.create(BackupKind.manual, "Точка возврата")

    async def _broken(object_key, local_path):
        raise backup.BackupError("pg_restore: повреждённый архив")

    monkeypatch.setattr(backup, "_swap_in_backup", _broken)

    result = await backup.restore(target["id"])

    assert result["status"] == "failed"
    run = await _row(target["id"])
    assert run.restore_status == BackupStatus.failed
    assert "повреждённый архив" in run.restore_detail


@pytest.mark.asyncio
async def test_restore_refuses_a_failed_copy(clean_runs, fake_dump, buckets, fake_swap):
    async with async_session_factory() as session:
        run = BackupRun(kind=BackupKind.hourly, status=BackupStatus.failed, object_key="hourly/x")
        session.add(run)
        await session.commit()
        run_id = run.id
    await engine.dispose()

    result = await backup.restore(run_id)

    assert result["status"] == "failed"
    assert fake_swap == []


@pytest.mark.asyncio
async def test_two_restores_at_once_are_refused(clean_runs, fake_dump, buckets, fake_swap):
    """Второй откат подменил бы базу под первым — так делать нельзя."""
    first = await backup.create(BackupKind.manual, "Первая")
    second = await backup.create(BackupKind.manual, "Вторая")
    await backup._set_restore_state(first["id"], BackupStatus.running, "откат начат")

    result = await backup.restore(second["id"])

    assert result["status"] == "busy"
    assert fake_swap == []


@pytest.mark.asyncio
async def test_a_stalled_restore_does_not_block_forever(clean_runs, fake_dump, buckets, fake_swap):
    """Оборвавшийся откат нельзя считать «выполняющимся» вечно.

    Иначе одна такая строка навсегда запирает кнопки в админке.
    """
    from datetime import UTC, datetime, timedelta

    stuck = await backup.create(BackupKind.manual, "Зависшая")
    fresh = await backup.create(BackupKind.manual, "Свежая")
    await backup._set_restore_state(stuck["id"], BackupStatus.running, "откат начат")
    async with async_session_factory() as session:
        row = await session.get(BackupRun, stuck["id"])
        row.restored_at = datetime.now(UTC) - timedelta(hours=3)
        await session.commit()
    await engine.dispose()

    assert backup.is_stalled(await _row(stuck["id"])) is True
    assert backup.is_stalled(await _row(fresh["id"])) is False

    # И новый откат такая строка блокировать не должна.
    assert (await backup.restore(fresh["id"]))["status"] == "ok"


@pytest.mark.asyncio
async def test_restore_refuses_a_deleted_copy(clean_runs, fake_dump, buckets, fake_swap):
    created = await backup.create(BackupKind.manual, "Удалённая")
    await backup.remove(created["id"])

    assert (await backup.restore(created["id"]))["status"] == "not_found"
    assert fake_swap == []
