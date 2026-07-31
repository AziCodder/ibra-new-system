from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderStatus
from app.models.user import User, UserRole


async def get_order_for_read(order_id: int, user: User, session: AsyncSession) -> Order:
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if user.role == UserRole.manager and order.manager_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


async def get_order_for_write(order_id: int, user: User, session: AsyncSession) -> Order:
    """Shared write-access guard for order sub-resources (products, logistics,
    payment requests, payments, ledger entries).

    Blocks observers, then blocks ANY role — including admin — from mutating a
    completed order's children: a completed order's profit snapshot is frozen,
    and silently letting it be edited (e.g. adding a product) desyncs that
    snapshot from reality. The order must be explicitly reverted to
    "in_progress" (POST /set-status) before it can be touched again.

    Notes are intentionally NOT routed through this guard — they don't feed the
    profit snapshot, so they stay editable on a completed order.
    """
    if user.role == UserRole.observer:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    order = await get_order_for_read(order_id, user, session)
    if order.status == OrderStatus.completed:
        raise HTTPException(
            status_code=409,
            detail="Order is completed; revert it to in-progress before editing",
        )
    return order
