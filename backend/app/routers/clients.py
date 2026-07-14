from fastapi import APIRouter, Depends, HTTPException
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.models.client import Client
from app.models.user import User, UserRole
from app.routers.auth import get_current_user, require_role
from app.schemas.client import ClientCreate, ClientOut, ClientUpdate
from app.services.telegram_bot import TG_LINK_SALT, TG_LINK_MAX_AGE

router = APIRouter(prefix="/api/clients", tags=["clients"])


@router.get("/", response_model=list[ClientOut])
async def list_clients(
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Client).order_by(Client.code))
    return result.scalars().all()


@router.post("/", response_model=ClientOut, status_code=201)
async def create_client(
    body: ClientCreate,
    _admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
):
    existing = await session.execute(select(Client).where(Client.code == body.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Client code already exists")

    client = Client(
        code=body.code,
        full_name=body.full_name,
        description=body.description,
        telegram_group_link=body.telegram_group_link,
        telegram_chat_id=body.telegram_chat_id,
    )
    session.add(client)
    await session.commit()
    await session.refresh(client)
    return client


@router.patch("/{client_id}", response_model=ClientOut)
async def update_client(
    client_id: int,
    body: ClientUpdate,
    _admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if body.full_name is not None:
        client.full_name = body.full_name
    if body.description is not None:
        client.description = body.description
    if body.telegram_group_link is not None:
        client.telegram_group_link = body.telegram_group_link
    if body.telegram_chat_id is not None:
        client.telegram_chat_id = body.telegram_chat_id

    await session.commit()
    await session.refresh(client)
    return client


@router.post("/{client_id}/telegram-link", response_model=dict)
async def generate_telegram_link(
    client_id: int,
    _admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    s = URLSafeTimedSerializer(settings.session_secret)
    token = s.dumps({"client_id": client_id}, salt=TG_LINK_SALT)
    return {"token": token, "expires_in_hours": TG_LINK_MAX_AGE // 3600}


@router.delete("/{client_id}", status_code=204)
async def delete_client(
    client_id: int,
    _admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    await session.delete(client)
    await session.commit()
