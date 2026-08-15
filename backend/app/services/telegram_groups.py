from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.telegram_group import ClientTelegramGroup, TelegramGroup


async def get_client_send_targets(client: Client, session: AsyncSession) -> list[dict]:
    """Telegram chats the admin attached to `client`, ordered by title.

    Chats the bot has been removed from are skipped — nothing can be delivered
    there, and offering them as a target would only produce silent failures.

    Empty list means 0 chats — callers fall back to client.telegram_chat_id
    (the private chat), exactly matching today's single-target behavior.
    """
    result = await session.execute(
        select(TelegramGroup.id, TelegramGroup.chat_id, TelegramGroup.title)
        .join(ClientTelegramGroup, ClientTelegramGroup.group_id == TelegramGroup.id)
        .where(ClientTelegramGroup.client_id == client.id, TelegramGroup.is_active.is_(True))
        .order_by(TelegramGroup.title)
    )
    return [{"group_id": row.id, "chat_id": row.chat_id, "title": row.title} for row in result.all()]
