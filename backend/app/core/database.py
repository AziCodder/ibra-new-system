from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# pool_pre_ping: соединение из пула проверяется перед выдачей. Без этого
# после любого разрыва (перезапуск БД, переключение на второй сервер, откат
# на резервную копию) первый же запрос падал бы на «мёртвом» соединении из
# пула вместо того, чтобы просто переподключиться.
engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
