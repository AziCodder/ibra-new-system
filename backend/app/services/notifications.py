import asyncio
import logging

from app.services import telegram_bot

logger = logging.getLogger("notifications")

# Strong references to in-flight background sends so they are not
# garbage-collected before completion (asyncio keeps only weak refs).
_background_tasks: set[asyncio.Task] = set()


def notify(target: str, message: str) -> None:
    """Fire-and-forget notification entry point (single integration point).

    Schedules background delivery (with retries) via the Telegram transport so
    the API response is never blocked (Итог 11.2). Retry/transport logic lives
    in app.services.telegram_bot.send_message_with_retries; scheduling it onto
    the running loop here gives a non-blocking send at the one place the hooks
    (6.5/7.6) call. When no bot is configured (dev/tests without a token) it
    only logs — no task is scheduled, so the token-less path stays a pure no-op.
    """
    logger.info("NOTIFY -> %s: %s", target or "(no target configured)", message)

    if telegram_bot.get_bot() is None:
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("notify: no running event loop; message to %s not scheduled", target)
        return

    task = loop.create_task(telegram_bot.send_message_with_retries(target, message))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
