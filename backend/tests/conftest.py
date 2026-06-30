import pytest_asyncio

from app.core.database import engine


@pytest_asyncio.fixture(autouse=True)
async def _dispose_engine_after_test():
    """Each pytest-asyncio test runs on its own event loop; the shared
    engine's connection pool must not carry connections across loops,
    or asyncpg raises 'another operation is in progress' / 'Event loop is closed'."""
    yield
    await engine.dispose()
