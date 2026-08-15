import asyncio

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory, engine
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.services import telegram_bot


@pytest.fixture(autouse=True)
def _no_live_telegram(monkeypatch):
    """Keep the suite off the real bot.

    The dev .env carries a working TELEGRAM_BOT_TOKEN, so without this every
    notify() in a test would open a live connection and try to deliver to the
    fake chat ids the fixtures invent. Tests that exercise the transport
    override this themselves (they patch get_bot / the send functions).
    """
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    monkeypatch.setattr(telegram_bot, "_bot", None)


@pytest.fixture(scope="session", autouse=True)
def _seed_admin_user():
    """Fresh CI DBs have no users; several tests expect at least one admin."""

    async def _seed() -> None:
        async with async_session_factory() as session:
            existing = (
                await session.execute(select(User).where(User.role == UserRole.admin).limit(1))
            ).scalar_one_or_none()
            if existing is None:
                session.add(
                    User(
                        login="test_admin",
                        password_hash=hash_password("test"),
                        role=UserRole.admin,
                        full_name="Test Admin",
                        is_active=True,
                    )
                )
                await session.commit()

    async def _run() -> None:
        await _seed()
        await engine.dispose()

    asyncio.run(_run())
    yield


@pytest_asyncio.fixture(autouse=True)
async def _dispose_engine_after_test():
    """Each pytest-asyncio test runs on its own event loop; the shared
    engine's connection pool must not carry connections across loops,
    or asyncpg raises 'another operation is in progress' / 'Event loop is closed'."""
    yield
    await engine.dispose()
