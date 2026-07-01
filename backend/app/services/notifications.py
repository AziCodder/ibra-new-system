import asyncio
import logging

from app.core.database import async_session_factory
from app.models.notification_log import NotificationLog, NotificationStatus
from app.services import telegram_bot

logger = logging.getLogger("notifications")

# Strong references to in-flight background sends so they are not
# garbage-collected before completion (asyncio keeps only weak refs).
_background_tasks: set[asyncio.Task] = set()


async def _record_delivery(target: str, message: str, delivered: bool, error: str) -> None:
    """Persist the outcome of one delivery attempt (Phase 11.5 visibility).

    Best-effort: a logging-store failure must never propagate out of the
    background task, so its own errors are caught and logged.
    """
    status = NotificationStatus.sent if delivered else NotificationStatus.failed
    try:
        async with async_session_factory() as session:
            session.add(
                NotificationLog(target=target or "", message=message, status=status, error=error)
            )
            await session.commit()
    except Exception:
        logger.exception("notify: could not persist delivery log for %s", target)


async def _deliver_and_log(target: str, message: str) -> None:
    """Deliver in the background and record the outcome; never raise.

    Transport-level failures are already caught inside
    telegram_bot.send_message_with_retries (returns False after retries); the
    broad guard here only defends against unexpected non-transport errors so a
    failed send degrades to a logged + persisted "failed" row instead of a
    crashed task.
    """
    delivered = False
    error = ""
    try:
        delivered = await telegram_bot.send_message_with_retries(target, message)
        if not delivered:
            error = "delivery failed after retries (see telegram log for detail)"
    except Exception as exc:  # noqa: BLE001 - background task must not crash
        error = str(exc)
        logger.exception("notify: unexpected error delivering to %s", target)
    await _record_delivery(target, message, delivered, error)


def notify(target: str, message: str) -> None:
    """Fire-and-forget notification entry point (single integration point).

    Schedules background delivery (with retries) via the Telegram transport so
    the API response is never blocked (Итог 11.2). Every delivery attempt is
    persisted to notification_logs so failures are visible (Итог 11.5). When no
    bot is configured (dev/tests without a token) it only logs — no task is
    scheduled and nothing is persisted, keeping the token-less path a pure no-op.
    """
    logger.info("NOTIFY -> %s: %s", target or "(no target configured)", message)

    if telegram_bot.get_bot() is None:
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("notify: no running event loop; message to %s not scheduled", target)
        return

    task = loop.create_task(_deliver_and_log(target, message))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
