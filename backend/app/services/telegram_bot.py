import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import AiogramError
from aiogram.filters import JOIN_TRANSITION, LEAVE_TRANSITION, ChatMemberUpdatedFilter, CommandStart
from aiogram.types import BufferedInputFile, ChatMemberUpdated, Message
from fastapi import BackgroundTasks
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.client import Client
from app.models.telegram_group import TelegramGroup

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


async def _upsert_group(session: AsyncSession, chat_id: str, title: str) -> TelegramGroup:
    """Find-or-create the TelegramGroup row for chat_id; refresh title if changed.

    Which clients a chat serves is the admin's call (see routers/telegram_groups.py);
    the bot only keeps the catalogue of chats it can reach up to date.
    """
    result = await session.execute(select(TelegramGroup).where(TelegramGroup.chat_id == chat_id))
    group = result.scalar_one_or_none()
    if group is None:
        group = TelegramGroup(chat_id=chat_id, title=title)
        session.add(group)
        await session.flush()
        return group
    if title and group.title != title:
        group.title = title
    group.is_active = True
    return group


def _get_dispatcher() -> Dispatcher:
    global _dp
    if _dp is not None:
        return _dp

    _dp = Dispatcher()

    @_dp.message(CommandStart())
    async def handle_start(message: Message) -> None:
        from app.core.database import async_session_factory

        chat_id = str(message.chat.id)
        args = (message.text or "").split(maxsplit=1)
        token = args[1].strip() if len(args) >= 2 and args[1].strip() else None

        if not token:
            async with async_session_factory() as session:
                result = await session.execute(select(Client).where(Client.telegram_chat_id == chat_id))
                linked_client = result.scalar_one_or_none()
            if linked_client is not None:
                await message.answer(
                    "✅ Этот чат уже привязан.\n\n"
                    f"<b>Код:</b> {linked_client.code}\n"
                    f"<b>ФИО:</b> {linked_client.full_name}",
                    parse_mode="HTML",
                )
                return
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

    @_dp.my_chat_member(
        F.chat.type.in_({"group", "supergroup"}),
        ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION),
    )
    async def handle_bot_added_to_group(event: ChatMemberUpdated) -> None:
        """Bot added to a chat -> the chat shows up in the admin's list, ready to
        be attached to clients. Adding the bot links nothing on its own."""
        from app.core.database import async_session_factory

        async with async_session_factory() as session:
            await _upsert_group(session, str(event.chat.id), event.chat.title or "")
            await session.commit()

    @_dp.my_chat_member(
        F.chat.type.in_({"group", "supergroup"}),
        ChatMemberUpdatedFilter(member_status_changed=LEAVE_TRANSITION),
    )
    async def handle_bot_removed_from_group(event: ChatMemberUpdated) -> None:
        """Bot removed -> the chat stops being a delivery target, but the client
        links the admin set stay, so re-adding the bot restores them."""
        from app.core.database import async_session_factory

        async with async_session_factory() as session:
            group = (
                await session.execute(select(TelegramGroup).where(TelegramGroup.chat_id == str(event.chat.id)))
            ).scalar_one_or_none()
            if group is not None:
                group.is_active = False
                await session.commit()

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
        # Cancelling is how polling is meant to end, so its CancelledError is
        # the expected outcome here, not a failure.
        with contextlib.suppress(asyncio.CancelledError):
            await _polling_task
        _polling_task = None
    logger.info("Telegram bot polling stopped")


async def send_message(chat_id: str | int, text: str) -> bool:
    bot = get_bot()
    if bot is None:
        logger.warning("Telegram bot token not configured; message to %s dropped", chat_id)
        return False
    await bot.send_message(chat_id=chat_id, text=text)
    return True


async def send_document(chat_id: str | int, filename: str, data: bytes) -> bool:
    bot = get_bot()
    if bot is None:
        logger.warning("Telegram bot token not configured; file %s to %s dropped", filename, chat_id)
        return False
    await bot.send_document(chat_id=chat_id, document=BufferedInputFile(data, filename=filename))
    return True


async def send_document_with_retries(
    chat_id: str | int,
    filename: str,
    data: bytes,
    *,
    max_retries: int = MAX_RETRIES,
    delay: float = RETRY_DELAY_SECONDS,
) -> bool:
    for attempt in range(1, max_retries + 1):
        try:
            delivered = await send_document(chat_id, filename, data)
        except AiogramError as exc:
            logger.warning(
                "Telegram file attempt %d/%d to %s failed: %s",
                attempt, max_retries, chat_id, exc,
            )
            if attempt < max_retries:
                await asyncio.sleep(delay)
                continue
            logger.error("Telegram file delivery to %s gave up after %d attempts", chat_id, max_retries)
            return False
        return delivered
    return False


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
