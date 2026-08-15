from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.client import Client
from app.models.telegram_group import ClientTelegramGroup, TelegramGroup
from app.services import telegram_bot

# A syntactically valid (but fake) bot token so aiogram's Bot() constructor accepts it.
FAKE_TOKEN = "123456789:AAEwABCDEFGHIJKLMNOPQRSTUVWXYZ0123456"


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Ensure the module-level bot singleton is clean before and after each test."""
    telegram_bot._bot = None
    yield
    telegram_bot._bot = None


def test_get_bot_returns_none_without_token(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    assert telegram_bot.get_bot() is None


def test_get_bot_creates_and_caches_single_instance(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", FAKE_TOKEN)
    bot_a = telegram_bot.get_bot()
    bot_b = telegram_bot.get_bot()
    assert bot_a is not None
    assert bot_a is bot_b  # same instance reused, not recreated


@pytest.mark.asyncio
async def test_send_message_calls_bot_send_message(monkeypatch):
    fake_bot = AsyncMock()
    monkeypatch.setattr(telegram_bot, "get_bot", lambda: fake_bot)

    result = await telegram_bot.send_message("-1001234567890", "Тестовое сообщение")

    assert result is True
    fake_bot.send_message.assert_awaited_once_with(chat_id="-1001234567890", text="Тестовое сообщение")


@pytest.mark.asyncio
async def test_send_message_returns_false_without_bot(monkeypatch):
    monkeypatch.setattr(telegram_bot, "get_bot", lambda: None)
    result = await telegram_bot.send_message("123", "hi")
    assert result is False


@pytest.mark.asyncio
async def test_close_bot_closes_session_and_resets(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", FAKE_TOKEN)
    bot = telegram_bot.get_bot()
    with patch.object(type(bot.session), "close", new=AsyncMock()) as mock_close:
        await telegram_bot.close_bot()
        mock_close.assert_awaited_once()
    assert telegram_bot._bot is None


@pytest.mark.asyncio
async def test_close_bot_is_idempotent_when_no_bot():
    telegram_bot._bot = None
    # Should not raise even when nothing was ever created.
    await telegram_bot.close_bot()
    assert telegram_bot._bot is None


@pytest.mark.asyncio
async def test_lifespan_closes_bot_on_shutdown():
    from app.main import app, lifespan

    with patch("app.main.close_bot", new=AsyncMock()) as mock_close:
        async with lifespan(app):
            pass
        mock_close.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_with_retries_succeeds_on_first_attempt(monkeypatch):
    send = AsyncMock(return_value=True)
    monkeypatch.setattr(telegram_bot, "send_message", send)

    result = await telegram_bot.send_message_with_retries("123", "hi")

    assert result is True
    send.assert_awaited_once_with("123", "hi")


@pytest.mark.asyncio
async def test_send_with_retries_retries_then_succeeds(monkeypatch):
    send = AsyncMock(side_effect=[TelegramNetworkError(method=None, message="boom"), True])
    monkeypatch.setattr(telegram_bot, "send_message", send)
    sleep = AsyncMock()
    monkeypatch.setattr(telegram_bot.asyncio, "sleep", sleep)

    result = await telegram_bot.send_message_with_retries("123", "hi", max_retries=3, delay=0)

    assert result is True
    assert send.await_count == 2
    sleep.assert_awaited_once()  # one backoff between the two attempts


@pytest.mark.asyncio
async def test_send_with_retries_gives_up_after_max(monkeypatch):
    send = AsyncMock(side_effect=TelegramNetworkError(method=None, message="boom"))
    monkeypatch.setattr(telegram_bot, "send_message", send)
    monkeypatch.setattr(telegram_bot.asyncio, "sleep", AsyncMock())

    result = await telegram_bot.send_message_with_retries("123", "hi", max_retries=3, delay=0)

    assert result is False
    assert send.await_count == 3  # tried exactly max_retries times, no infinite loop


@pytest.mark.asyncio
async def test_send_with_retries_no_bot_does_not_retry(monkeypatch):
    # send_message returns False (no token) — a permanent condition, must not retry.
    send = AsyncMock(return_value=False)
    monkeypatch.setattr(telegram_bot, "send_message", send)
    sleep = AsyncMock()
    monkeypatch.setattr(telegram_bot.asyncio, "sleep", sleep)

    result = await telegram_bot.send_message_with_retries("123", "hi", max_retries=3, delay=0)

    assert result is False
    send.assert_awaited_once()  # single attempt only
    sleep.assert_not_awaited()


def test_queue_message_defers_delivery_to_background_tasks():
    from fastapi import BackgroundTasks

    bg = BackgroundTasks()
    telegram_bot.queue_message(bg, "-100999", "later")

    assert len(bg.tasks) == 1
    task = bg.tasks[0]
    assert task.func is telegram_bot.send_message_with_retries
    assert task.args == ("-100999", "later")


@pytest.mark.asyncio
async def test_client_persists_telegram_chat_id():
    async with async_session_factory() as session:
        client = Client(
            code="TSTTGB",
            full_name="Telegram Bot Client",
            telegram_group_link="https://t.me/+abc",
            telegram_chat_id="-1009876543210",
        )
        session.add(client)
        await session.commit()
        await session.refresh(client)
        client_id = client.id

    try:
        async with async_session_factory() as session:
            loaded = (await session.execute(select(Client).where(Client.id == client_id))).scalar_one()
            assert loaded.telegram_chat_id == "-1009876543210"
            assert loaded.telegram_group_link == "https://t.me/+abc"
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(Client).where(Client.id == client_id))
            await session.commit()


@pytest.mark.asyncio
async def test_upsert_group_creates_then_reuses_row():
    async with async_session_factory() as session:
        group1 = await telegram_bot._upsert_group(session, "-100111222", "Old Title")
        await session.commit()
        group1_id = group1.id

    try:
        async with async_session_factory() as session:
            group2 = await telegram_bot._upsert_group(session, "-100111222", "New Title")
            await session.commit()
            assert group2.id == group1_id
            assert group2.title == "New Title"

        async with async_session_factory() as session:
            loaded = (await session.execute(select(TelegramGroup).where(TelegramGroup.id == group1_id))).scalar_one()
            assert loaded.title == "New Title"
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(TelegramGroup).where(TelegramGroup.id == group1_id))
            await session.commit()


@pytest.mark.asyncio
async def test_upsert_group_reactivates_a_chat_the_bot_was_removed_from():
    """Re-adding the bot makes the chat deliverable again, links and all."""
    async with async_session_factory() as session:
        group = TelegramGroup(chat_id="-100999888", title="Kicked Group", is_active=False)
        session.add(group)
        await session.commit()
        await session.refresh(group)
        group_id = group.id

    try:
        async with async_session_factory() as session:
            await telegram_bot._upsert_group(session, "-100999888", "Kicked Group")
            await session.commit()

        async with async_session_factory() as session:
            loaded = (
                await session.execute(select(TelegramGroup).where(TelegramGroup.id == group_id))
            ).scalar_one()
            assert loaded.is_active is True
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(TelegramGroup).where(TelegramGroup.id == group_id))
            await session.commit()
