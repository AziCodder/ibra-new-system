import logging

from aiogram import Bot

from app.core.config import settings

logger = logging.getLogger("telegram")

_bot: Bot | None = None


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


async def close_bot() -> None:
    """Close the shared bot's aiohttp session on shutdown (idempotent)."""
    global _bot
    if _bot is not None:
        await _bot.session.close()
        _bot = None
