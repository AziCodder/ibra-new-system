import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.exceptions import AiogramError
from aiogram.filters import CommandStart
from aiogram.types import Message
from fastapi import BackgroundTasks
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select

from app.core.config import settings

logger = logging.getLogger("telegram")

_bot: Bot | None = None
_dp: Dispatcher | None = None
_polling_task: asyncio.Task | None = None

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2.0

TG_LINK_SALT = "tg-client-link"
TG_LINK_MAX_AGE = 86400  # 24 hours


def get_bot() -> Bot | None:
    global _bot
    if not settings.telegram_bot_token:
        return None
    if _bot is None:
        _bot = Bot(token=settings.telegram_bot_token)
    return _bot


def _get_dispatcher() -> Dispatcher:
    global _dp
    if _dp is not None:
        return _dp

    _dp = Dispatcher()

    @_dp.message(CommandStart())
    async def handle_start(message: Message) -> None:
        from app.core.database import async_session_factory
        from app.models.client import Client

        args = (message.text or "").split(maxsplit=1)
        token = args[1].strip() if len(args) >= 2 and args[1].strip() else None

        if not token:
            await message.answer(
                "👋 Привет! Я бот для уведомлений.\n\n"
                "Попросите администратора сгенерировать токен привязки "
                "и отправьте команду:\n<code>/start ВАШ_ТОКЕН</code>",
                parse_mode="HTML",
            )
            return

        s = URLSafeTimedSerializer(settings.session_secret)
        try:
            data = s.loads(token, salt=TG_LINK_SALT, max_age=TG_LINK_MAX_AGE)
            client_id = int(data["client_id"])
        except SignatureExpired:
            await message.answer("❌ Токен устарел. Попросите администратора сгенерировать новый.")
            return
        except (BadSignature, KeyError, ValueError):
            await message.answer("❌ Неверный токен. Проверьте команду и попробуйте снова.")
            return

        chat_id = str(message.chat.id)

        async with async_session_factory() as session:
            existing = await session.execute(
                select(Client).where(
                    Client.telegram_chat_id == chat_id,
                    Client.id != client_id,
                )
            )
            if existing.scalar_one_or_none():
                await message.answer("❌ Этот чат уже привязан к другому клиенту.")
                return

            result = await session.execute(select(Client).where(Client.id == client_id))
            client = result.scalar_one_or_none()
            if not client:
                await message.answer("❌ Клиент не найден.")
                return

            client.telegram_chat_id = chat_id
            await session.commit()
            client_name = client.full_name

        await message.answer(
            f"✅ Чат успешно привязан к клиенту <b>{client_name}</b>! "
            "Теперь вы будете получать уведомления здесь.",
            parse_mode="HTML",
        )

    return _dp


async def start_polling() -> None:
    bot = get_bot()
    if bot is None:
        logger.info("Telegram polling skipped: no token configured")
        return
    dp = _get_dispatcher()
    global _polling_task
    _polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
    logger.info("Telegram bot polling started")


async def stop_polling() -> None:
    global _polling_task
    if _polling_task is not None and not _polling_task.done():
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass
        _polling_task = None
    logger.info("Telegram bot polling stopped")


async def send_message(chat_id: str | int, text: str) -> bool:
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
    background_tasks.add_task(send_message_with_retries, chat_id, text)


async def close_bot() -> None:
    global _bot
    if _bot is not None:
        await _bot.session.close()
        _bot = None
