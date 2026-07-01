from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.client import Client
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
