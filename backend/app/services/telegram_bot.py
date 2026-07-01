import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import AiogramError
from fastapi import BackgroundTasks

from app.core.config import settings

logger = logging.getLogger("telegram")

_bot: Bot | None = None

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2.0


def get_bot() -> Bot | None:
    """Return the shared aiogram Bot instance, or None if no token is configured.

    A single Bot is created lazily and reused for all outbound messages
    (outgoing only — no polling/dispatcher). Its aiohttp session is closed
    on application shutdown via close_bot() from the FastAPI lifespan.
    """
    global _bot
    if not settings.telegram_bot_token:
        return None
    if _bot is None:
        _bot = Bot(token=settings.telegram_bot_token)
    return _bot


async def send_message(chat_id: str | int, text: str) -> bool:
    """Send one message through the shared bot.

    Returns True if dispatched, False if no bot is configured. This is the
    minimal direct send; Phase 11.2 wraps it with background delivery + retries
    and 11.5 adds failure handling.
    """
    bot = get_bot()
    if bot is None:
        logger.warning("Telegram bot token not configured; message to %s dropped", chat_id)
        return False
    await bot.send_message(chat_id=chat_id, text=text)
    return True


async def send_message_with_retries(
    chat_id: str | int,
    text: str,
    *,
    max_retries: int = MAX_RETRIES,
    delay: float = RETRY_DELAY_SECONDS,
) -> bool:
    """Deliver a message, retrying transient Telegram failures.

    Returns True once delivered. Returns False immediately when no bot is
    configured (not a transient condition, so it is not retried). Transient
    aiogram errors (network/server/rate-limit) are retried up to ``max_retries``
    times with a fixed ``delay`` between attempts; the final failure is swallowed
    and logged so a background task never crashes the worker.
    """
    for attempt in range(1, max_retries + 1):
        try:
            delivered = await send_message(chat_id, text)
        except AiogramError as exc:
            logger.warning(
                "Telegram send attempt %d/%d to %s failed: %s",
                attempt, max_retries, chat_id, exc,
            )
            if attempt < max_retries:
                await asyncio.sleep(delay)
                continue
            logger.error("Telegram delivery to %s gave up after %d attempts", chat_id, max_retries)
            return False
        return delivered
    return False


def queue_message(background_tasks: BackgroundTasks, chat_id: str | int, text: str) -> None:
    """Schedule background delivery so it runs after the API response is sent.

    Uses FastAPI BackgroundTasks: the outbound send (with retries) is deferred
    until the response has been returned, so notifying a client never blocks or
    slows the request that triggered it.
    """
    background_tasks.add_task(send_message_with_retries, chat_id, text)


async def close_bot() -> None:
    """Close the shared bot's aiohttp session on shutdown (idempotent)."""
    global _bot
    if _bot is not None:
        await _bot.session.close()
        _bot = None
