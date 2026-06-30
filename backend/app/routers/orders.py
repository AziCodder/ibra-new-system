from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.client import Client
from app.models.order import Order, OrderStatus
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.order import OrderCreate, OrderOut
from app.services.order_number import generate_order_number

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.post("/", response_model=OrderOut, status_code=201)
async def create_order(
    body: OrderCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    client_result = await session.execute(select(Client).where(Client.id == body.client_id))
    if not client_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Client not found")

    number = await generate_order_number(session, body.client_id)
    order = Order(
        number=number,
        client_id=body.client_id,
        manager_id=user.id,
        status=OrderStatus.in_progress,
        currency=body.currency,
        details=body.details,
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: int,
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
