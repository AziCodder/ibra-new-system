from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.client import Client
from app.models.telegram_group import ClientTelegramGroup, TelegramGroup
from app.models.user import User, UserRole
from app.routers.auth import require_role
from app.schemas.telegram_group import TelegramGroupAdminOut, TelegramGroupClientsIn

router = APIRouter(prefix="/api/telegram-groups", tags=["telegram_groups"])


async def _get_group_or_404(group_id: int, session: AsyncSession) -> TelegramGroup:
    group = (
        await session.execute(select(TelegramGroup).where(TelegramGroup.id == group_id))
    ).scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Telegram group not found")
    return group


async def _client_ids_of(group_id: int, session: AsyncSession) -> list[int]:
    rows = await session.execute(
        select(ClientTelegramGroup.client_id).where(ClientTelegramGroup.group_id == group_id)
    )
    return sorted(rows.scalars().all())


@router.get("/", response_model=list[TelegramGroupAdminOut])
async def list_telegram_groups(
    _admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
) -> list[TelegramGroupAdminOut]:
    """Every chat the bot has ever been added to, newest first.

    Chats appear here on their own: adding the bot to a chat registers it (see
    telegram_bot.handle_bot_added_to_group). Which clients it serves is set here.
    """
    groups = (
        await session.execute(select(TelegramGroup).order_by(TelegramGroup.created_at.desc()))
    ).scalars().all()

    links = (await session.execute(select(ClientTelegramGroup))).scalars().all()
    clients_by_group: dict[int, list[int]] = {}
    for link in links:
        clients_by_group.setdefault(link.group_id, []).append(link.client_id)

    return [
        TelegramGroupAdminOut(
            id=g.id,
            chat_id=g.chat_id,
            title=g.title,
            is_active=g.is_active,
            client_ids=sorted(clients_by_group.get(g.id, [])),
            created_at=g.created_at,
        )
        for g in groups
    ]


@router.put("/{group_id}/clients", response_model=TelegramGroupAdminOut)
async def set_telegram_group_clients(
    group_id: int,
    body: TelegramGroupClientsIn,
    _admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
) -> TelegramGroupAdminOut:
    """Replace the chat's client list with exactly `client_ids`.

    Sending the whole set rather than add/remove calls keeps the UI's checkbox
    list and the stored links from drifting apart when two admins edit at once.
    """
    group = await _get_group_or_404(group_id, session)

    wanted = set(body.client_ids)
    if wanted:
        found = set(
            (await session.execute(select(Client.id).where(Client.id.in_(wanted)))).scalars().all()
        )
        missing = wanted - found
        if missing:
            raise HTTPException(status_code=422, detail=f"Unknown client ids: {sorted(missing)}")

    current = set(await _client_ids_of(group_id, session))

    to_remove = current - wanted
    if to_remove:
        await session.execute(
            delete(ClientTelegramGroup).where(
                ClientTelegramGroup.group_id == group_id,
                ClientTelegramGroup.client_id.in_(to_remove),
            )
        )
    for client_id in sorted(wanted - current):
        session.add(ClientTelegramGroup(client_id=client_id, group_id=group_id))

    await session.commit()

    return TelegramGroupAdminOut(
        id=group.id,
        chat_id=group.chat_id,
        title=group.title,
        is_active=group.is_active,
        client_ids=sorted(wanted),
        created_at=group.created_at,
    )


@router.delete("/{group_id}", status_code=204)
async def delete_telegram_group(
    group_id: int,
    _admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Forget a chat entirely, with its client links.

    For chats the bot will never be in again — if the bot is still there, it will
    register the chat again on the next event.
    """
    group = await _get_group_or_404(group_id, session)
    await session.execute(delete(ClientTelegramGroup).where(ClientTelegramGroup.group_id == group_id))
    await session.delete(group)
    await session.commit()
