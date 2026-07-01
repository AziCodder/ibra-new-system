from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.models.notification_log import NotificationLog, NotificationStatus
from app.models.user import User, UserRole
from app.routers.notifications import list_notification_log
from app.services import notifications

TARGET = "TSTNLOG-group"


async def _purge():
    async with async_session_factory() as session:
        await session.execute(delete(NotificationLog).where(NotificationLog.target == TARGET))
        await session.commit()


async def _rows() -> list[NotificationLog]:
    async with async_session_factory() as session:
        return list(
            (
                await session.execute(
                    select(NotificationLog).where(NotificationLog.target == TARGET)
                )
            )
            .scalars()
            .all()
        )


@pytest.mark.asyncio
async def test_record_delivery_persists_sent_row():
    await _purge()
    await notifications._record_delivery(TARGET, "hello", delivered=True, error="")
    rows = await _rows()
    assert len(rows) == 1
    assert rows[0].status == NotificationStatus.sent
    assert rows[0].error == ""


@pytest.mark.asyncio
async def test_deliver_and_log_records_failed_when_send_returns_false(monkeypatch):
    await _purge()
    monkeypatch.setattr(
        notifications.telegram_bot, "send_message_with_retries", AsyncMock(return_value=False)
    )
    await notifications._deliver_and_log(TARGET, "hello")
    rows = await _rows()
    assert len(rows) == 1
    assert rows[0].status == NotificationStatus.failed
    assert "retries" in rows[0].error  # the "не доставлено" indicator carries a reason


@pytest.mark.asyncio
async def test_deliver_and_log_does_not_crash_on_unexpected_error(monkeypatch):
    monkeypatch.setattr(
        notifications.telegram_bot,
        "send_message_with_retries",
        AsyncMock(side_effect=RuntimeError("boom")),
    )
    await _purge()
    # Must not raise — a failed send degrades to a persisted "failed" row.
    await notifications._deliver_and_log(TARGET, "hello")
    rows = await _rows()
    assert len(rows) == 1
    assert rows[0].status == NotificationStatus.failed
    assert "boom" in rows[0].error


@pytest.mark.asyncio
async def test_admin_endpoint_lists_and_filters_by_status():
    await _purge()
    await notifications._record_delivery(TARGET, "ok", delivered=True, error="")
    await notifications._record_delivery(TARGET, "bad", delivered=False, error="down")
    admin = User(id=1, login="a", password_hash="x", role=UserRole.admin, full_name="Admin")

    async with async_session_factory() as session:
        all_rows = await list_notification_log(status=None, limit=100, _admin=admin, session=session)
        mine = [r for r in all_rows if r.target == TARGET]
        assert len(mine) == 2

    async with async_session_factory() as session:
        failed = await list_notification_log(
            status=NotificationStatus.failed, limit=100, _admin=admin, session=session
        )
        mine_failed = [r for r in failed if r.target == TARGET]
        assert len(mine_failed) == 1
        assert mine_failed[0].message == "bad"
