from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.telegram_group import ClientTelegramGroup, TelegramGroup


async def get_client_send_targets(client: Client, session: AsyncSession) -> list[dict]:
    """Telegram groups `client` is linked to, ordered by title.

    Empty list means 0 groups — callers fall back to client.telegram_chat_id
    (the private chat), exactly matching today's single-target behavior.
    """
    result = await session.execute(
        select(TelegramGroup.id, TelegramGroup.chat_id, TelegramGroup.title)
        .join(ClientTelegramGroup, ClientTelegramGroup.group_id == TelegramGroup.id)
        .where(ClientTelegramGroup.client_id == client.id)
        .order_by(TelegramGroup.title)
    )
    return [{"group_id": row.id, "chat_id": row.chat_id, "title": row.title} for row in result.all()]
