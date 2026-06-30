from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.client import Client
from app.models.order import Order, OrderStatus
from app.models.user import User, UserRole
from app.routers.auth import get_current_user, require_role
from app.schemas.order import OrderCreate, OrderListOut, OrderOut, OrderUpdate
from app.services.order_dependencies import count_order_dependencies
from app.services.order_number import generate_order_number

router = APIRouter(prefix="/api/orders", tags=["orders"])


def _to_order_out(order: Order, client_name: str, manager_name: str) -> OrderOut:
    return OrderOut(
        id=order.id,
        number=order.number,
        client_id=order.client_id,
        client_name=client_name,
        manager_id=order.manager_id,
        manager_name=manager_name,
        status=order.status,
        currency=order.currency,
        details=order.details,
        created_at=order.created_at,
        profit_pct=order.profit_pct,
        processing_days=order.processing_days,
    )


@router.post("/", response_model=OrderOut, status_code=201)
async def create_order(
    body: OrderCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    client_result = await session.execute(select(Client).where(Client.id == body.client_id))
    client = client_result.scalar_one_or_none()
    if not client:
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
    return _to_order_out(order, client.full_name, user.full_name)


@router.get("/", response_model=OrderListOut)
async def list_orders(
    client_id: int | None = None,
    status: OrderStatus | None = None,
    manager_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # Managers only ever see their own orders, regardless of requested manager_id
    if user.role == UserRole.manager:
        manager_id = user.id

    filters = []
    if client_id is not None:
        filters.append(Order.client_id == client_id)
    if status is not None:
        filters.append(Order.status == status)
    if manager_id is not None:
        filters.append(Order.manager_id == manager_id)

    count_query = select(func.count()).select_from(Order)
    list_query = (
        select(Order, Client.full_name, User.full_name)
        .join(Client, Order.client_id == Client.id)
        .join(User, Order.manager_id == User.id)
        .order_by(Order.id.desc())
    )
    for f in filters:
        count_query = count_query.where(f)
        list_query = list_query.where(f)

    total = (await session.execute(count_query)).scalar_one()
    list_query = list_query.offset((page - 1) * page_size).limit(page_size)
    rows = (await session.execute(list_query)).all()
    items = [_to_order_out(order, client_name, manager_name) for order, client_name, manager_name in rows]

    return OrderListOut(items=items, total=total, page=page, page_size=page_size)


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Order, Client.full_name, User.full_name)
        .join(Client, Order.client_id == Client.id)
        .join(User, Order.manager_id == User.id)
        .where(Order.id == order_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    order, client_name, manager_name = row
    if user.role == UserRole.manager and order.manager_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    return _to_order_out(order, client_name, manager_name)


@router.patch("/{order_id}", response_model=OrderOut)
async def update_order(
    order_id: int,
    body: OrderUpdate,
    _admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Order, Client.full_name, User.full_name)
        .join(Client, Order.client_id == Client.id)
        .join(User, Order.manager_id == User.id)
        .where(Order.id == order_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    order, client_name, manager_name = row

    order.details = body.details
    await session.commit()
    await session.refresh(order)
    return _to_order_out(order, client_name, manager_name)


@router.delete("/{order_id}", status_code=204)
async def delete_order(
    order_id: int,
    _admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    dependency_count = await count_order_dependencies(session, order_id)
    if dependency_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Order has {dependency_count} related record(s) and cannot be deleted",
        )

    await session.delete(order)
    await session.commit()
