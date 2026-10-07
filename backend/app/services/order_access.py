from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderStatus
from app.models.user import User, UserRole

# In Russian: several frontend API modules show a backend detail verbatim, and these
# can surface from any page that edits an order's records.
ORDER_CALCULATED_DETAIL = "Заказ рассчитан и заморожен — чтобы что-то изменить, сначала отмените расчёт"
ORDER_COMPLETED_DETAIL = "Заказ завершён — чтобы что-то изменить, сначала верните его в работу"


async def get_order_for_read(order_id: int, user: User, session: AsyncSession) -> Order:
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if user.role == UserRole.manager and order.manager_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def ensure_not_calculated(order: Order) -> None:
    """Freeze a calculated order for every role, admin included.

    Its profit has already been shared out between people, so nothing the order is
    made of — goods, payments, logistics, notes, comments, files, details, status —
    may change until an admin cancels the calculation. Wider than the completed-order
    lock below, which deliberately leaves notes and comments open.
    """
    if order.calculated_at is not None:
        raise HTTPException(status_code=409, detail=ORDER_CALCULATED_DETAIL)


async def get_order_for_write(order_id: int, user: User, session: AsyncSession) -> Order:
    """Shared write-access guard for order sub-resources (products, logistics,
    payment requests, payments, ledger entries).

    Blocks observers, then blocks ANY role — including admin — from mutating a
    completed order's children: a completed order's profit snapshot is frozen,
    and silently letting it be edited (e.g. adding a product) desyncs that
    snapshot from reality. The order must be explicitly reverted to
    "in_progress" (POST /set-status) before it can be touched again.

    Notes are intentionally NOT routed through this guard — they don't feed the
    profit snapshot, so they stay editable on a completed order (but not on a
    calculated one, see ensure_not_calculated).
    """
    if user.role == UserRole.observer:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    order = await get_order_for_read(order_id, user, session)
    ensure_not_calculated(order)
    if order.status == OrderStatus.completed:
        raise HTTPException(status_code=409, detail=ORDER_COMPLETED_DETAIL)
    return order
