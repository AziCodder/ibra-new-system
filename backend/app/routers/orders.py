from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import case, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.client import Client
from app.models.order import Order, OrderStatus
from app.models.order_sort_position import OrderSortPosition
from app.models.user import User, UserRole
from app.routers.auth import get_current_user, require_role
from app.schemas.order import (
    MAX_ORDER_FILES,
    OrderCreate,
    OrderFileAdd,
    OrderListOut,
    OrderOut,
    OrderReorderIn,
    OrderStatsOut,
    OrderUpdate,
)
from app.services.action_log import log_action
from app.services.order_access import get_order_for_write as _get_order_for_write
from app.services.order_completion import check_can_complete
from app.services.order_dependencies import order_dependency_breakdown
from app.services.order_metrics import snapshot_order_metrics
from app.services.order_number import generate_order_number
from app.services.order_payment_summary import get_orders_payment_totals

router = APIRouter(prefix="/api/orders", tags=["orders"])


def _to_order_out(
    order: Order,
    client_name: str,
    manager_name: str,
    payment_totals: tuple[Decimal, Decimal] | None = None,
) -> OrderOut:
    requested_amount, paid_amount = payment_totals if payment_totals else (None, None)
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
        file_keys=order.file_keys,
        created_at=order.created_at,
        completed_at=order.completed_at,
        profit_pct=order.profit_pct,
        processing_days=order.processing_days,
        total_income=order.total_income,
        profit_amount=order.profit_amount,
        requested_amount=requested_amount,
        paid_amount=paid_amount,
    )


@router.post("/", response_model=OrderOut, status_code=201)
async def create_order(
    body: OrderCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if user.role == UserRole.observer:
        raise HTTPException(status_code=403, detail="Observers cannot create orders")

    client_result = await session.execute(select(Client).where(Client.id == body.client_id))
    client = client_result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    manager_id = user.id
    manager_name = user.full_name
    if body.manager_id is not None and body.manager_id != user.id:
        if user.role != UserRole.admin:
            raise HTTPException(status_code=403, detail="Only admins can assign a different manager")
        manager = (await session.execute(select(User).where(User.id == body.manager_id))).scalar_one_or_none()
        if not manager:
            raise HTTPException(status_code=404, detail="Manager not found")
        if manager.role not in (UserRole.manager, UserRole.admin):
            raise HTTPException(status_code=422, detail="Target user must have the manager or admin role")
        manager_id = manager.id
        manager_name = manager.full_name

    number = await generate_order_number(session, body.client_id)
    order = Order(
        number=number,
        client_id=body.client_id,
        manager_id=manager_id,
        status=OrderStatus.in_progress,
        currency=body.currency,
        details=body.details,
        file_keys=body.file_keys,
    )
    session.add(order)
    await session.flush()  # assign order.id before logging
    await log_action(session, user, "order.created", "order", order.id, f"№{order.number}")
    await session.commit()
    await session.refresh(order)
    return _to_order_out(order, client.full_name, manager_name)


@router.get("/", response_model=OrderListOut)
async def list_orders(
    client_id: int | None = None,
    status: OrderStatus | None = None,
    manager_id: int | None = None,
    search: str | None = None,
    sort_by: Literal["created_at", "number", "manual"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
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
    if search:
        like = f"%{search.strip()}%"
        filters.append(or_(Order.number.ilike(like), Client.full_name.ilike(like)))

    count_query = select(func.count()).select_from(Order).join(Client, Order.client_id == Client.id)
    list_query = (
        select(Order, Client.full_name, User.full_name)
        .join(Client, Order.client_id == Client.id)
        .join(User, Order.manager_id == User.id)
    )

    if sort_by == "manual":
        # Ручной порядок ПЕРСОНАЛЬНЫЙ: позиции текущего пользователя. Заказы без
        # сохранённой позиции (созданные после последней перестановки) идут
        # сверху и новыми вперёд — иначе новый заказ затерялся бы в конце списка.
        list_query = list_query.outerjoin(
            OrderSortPosition,
            (OrderSortPosition.order_id == Order.id) & (OrderSortPosition.user_id == user.id),
        ).order_by(
            case((OrderSortPosition.position.is_(None), 0), else_=1),
            OrderSortPosition.position.asc(),
            Order.id.desc(),
        )
    else:
        sort_column = Order.number if sort_by == "number" else Order.created_at
        direction = sort_column.asc() if sort_order == "asc" else sort_column.desc()
        list_query = list_query.order_by(direction, Order.id.desc())

    for f in filters:
        count_query = count_query.where(f)
        list_query = list_query.where(f)

    total = (await session.execute(count_query)).scalar_one()
    list_query = list_query.offset((page - 1) * page_size).limit(page_size)
    rows = (await session.execute(list_query)).all()

    order_ids = [order.id for order, _, _ in rows]
    payment_totals = await get_orders_payment_totals(session, order_ids)
    items = [
        _to_order_out(order, client_name, manager_name, payment_totals.get(order.id))
        for order, client_name, manager_name in rows
    ]

    return OrderListOut(items=items, total=total, page=page, page_size=page_size)


@router.post("/reorder", status_code=204, response_model=None)
async def reorder_orders(
    body: OrderReorderIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Сохранить ручной порядок заказов для текущего пользователя.

    Порядок ПЕРСОНАЛЬНЫЙ — у остальных пользователей он не меняется, поэтому
    перестановка не пишется в журнал действий. Фронтенд присылает id заказов
    видимой страницы в новом порядке; позиции пересчитываются по всему списку
    доступных пользователю заказов, чтобы порядок оставался согласованным
    между страницами пагинации. Ответ не сериализуется — фронтенд
    перезапрашивает список.
    """
    submitted = body.order_ids
    if not submitted:
        return
    if len(set(submitted)) != len(submitted):
        raise HTTPException(status_code=422, detail="Duplicate order ids in the request")

    # Менеджер видит только свои заказы — и переставлять может только их.
    scope = [Order.manager_id == user.id] if user.role == UserRole.manager else []
    visible_ids = [row[0] for row in (await session.execute(select(Order.id).where(*scope))).all()]
    if set(submitted) - set(visible_ids):
        raise HTTPException(status_code=404, detail="Order not found")

    saved_positions = dict(
        (
            await session.execute(
                select(OrderSortPosition.order_id, OrderSortPosition.position).where(
                    OrderSortPosition.user_id == user.id
                )
            )
        ).all()
    )
    # Текущий персональный порядок целиком — тот же, что отдаёт sort_by=manual:
    # сначала заказы без позиции (новые вперёд), затем расставленные по position.
    full_order = sorted(
        visible_ids,
        key=lambda order_id: (1, saved_positions[order_id], 0)
        if order_id in saved_positions
        else (0, 0, -order_id),
    )
    # Присланные заказы занимают те же места в общем списке, но в новом порядке —
    # так перестановка внутри страницы не задевает заказы с других страниц.
    slots = [i for i, order_id in enumerate(full_order) if order_id in set(submitted)]
    for slot, order_id in zip(slots, submitted, strict=True):
        full_order[slot] = order_id

    await session.execute(delete(OrderSortPosition).where(OrderSortPosition.user_id == user.id))
    session.add_all(
        [
            OrderSortPosition(user_id=user.id, order_id=order_id, position=index)
            for index, order_id in enumerate(full_order)
        ]
    )
    await session.commit()


@router.get("/stats", response_model=OrderStatsOut)
async def get_order_stats(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    base_filters = []
    if user.role == UserRole.manager:
        base_filters.append(Order.manager_id == user.id)

    now = datetime.now(UTC)
    month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
    if now.month == 1:
        prev_month_start = datetime(now.year - 1, 12, 1, tzinfo=UTC)
    else:
        prev_month_start = datetime(now.year, now.month - 1, 1, tzinfo=UTC)

    async def count_where(*extra) -> int:
        q = select(func.count()).select_from(Order)
        for f in (*base_filters, *extra):
            q = q.where(f)
        return (await session.execute(q)).scalar_one()

    total_count = await count_where()
    total_count_delta_month = await count_where(Order.created_at >= month_start)
    in_progress_count = await count_where(Order.status == OrderStatus.in_progress)
    completed_count = await count_where(Order.status == OrderStatus.completed)
    completed_created_this_month = await count_where(
        Order.status == OrderStatus.completed, Order.created_at >= month_start
    )
    completed_pct_month = (
        round(completed_created_this_month / total_count_delta_month * 100, 1)
        if total_count_delta_month > 0
        else None
    )

    # "Waiting payment" = in-progress orders whose payment requests still have a remaining balance.
    in_progress_ids_query = select(Order.id).where(*base_filters, Order.status == OrderStatus.in_progress)
    in_progress_ids = [row[0] for row in (await session.execute(in_progress_ids_query)).all()]
    payment_totals = await get_orders_payment_totals(session, in_progress_ids)
    waiting_payment_count = sum(1 for requested, paid in payment_totals.values() if requested - paid > 0)

    async def profit_sum_for(start: datetime, end: datetime) -> dict[str, Decimal]:
        rows = (
            await session.execute(
                select(Order.currency, func.sum(Order.profit_amount))
                .where(
                    *base_filters,
                    Order.completed_at.is_not(None),
                    Order.completed_at >= start,
                    Order.completed_at < end,
                    Order.profit_amount.is_not(None),
                )
                .group_by(Order.currency)
            )
        ).all()
        return {currency: amount for currency, amount in rows}

    profit_month = await profit_sum_for(month_start, now)
    profit_prev_month = await profit_sum_for(prev_month_start, month_start)

    leading_currency = max(profit_month, key=lambda c: profit_month[c]) if profit_month else None
    profit_month_delta_pct: float | None = None
    if leading_currency:
        prev_amount = profit_prev_month.get(leading_currency)
        if prev_amount:
            profit_month_delta_pct = round(
                float((profit_month[leading_currency] - prev_amount) / prev_amount * 100), 1
            )

    return OrderStatsOut(
        total_count=total_count,
        total_count_delta_month=total_count_delta_month,
        in_progress_count=in_progress_count,
        waiting_payment_count=waiting_payment_count,
        completed_count=completed_count,
        completed_pct_month=completed_pct_month,
        profit_month=profit_month,
        profit_month_delta_pct=profit_month_delta_pct,
    )


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
    payment_totals = await get_orders_payment_totals(session, [order.id])
    return _to_order_out(order, client_name, manager_name, payment_totals.get(order.id))


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

    if body.manager_id is not None and body.manager_id != order.manager_id:
        manager = (await session.execute(select(User).where(User.id == body.manager_id))).scalar_one_or_none()
        if not manager:
            raise HTTPException(status_code=404, detail="Manager not found")
        if manager.role not in (UserRole.manager, UserRole.admin):
            raise HTTPException(status_code=422, detail="Target user must have the manager or admin role")
        order.manager_id = manager.id
        manager_name = manager.full_name

    await session.commit()
    await session.refresh(order)
    return _to_order_out(order, client_name, manager_name)


class OrderStatusIn(BaseModel):
    status: OrderStatus


@router.post("/{order_id}/set-status", response_model=OrderOut)
async def set_order_status(
    order_id: int,
    body: OrderStatusIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Change order status according to ТЗ §13 transition rules.

    Allowed transitions:
    - in_progress → completed:  admin only, requires check_can_complete
    - in_progress → cancelled:  admin or manager (own order)
    - cancelled   → in_progress: admin only
    - completed   → in_progress: admin only
    - completed   → cancelled:  forbidden (409)
    """
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

    if user.role == UserRole.observer:
        raise HTTPException(status_code=403, detail="Observers cannot change order status")

    current = order.status
    target = body.status

    if current == target:
        return _to_order_out(order, client_name, manager_name)

    if current == OrderStatus.completed and target == OrderStatus.cancelled:
        raise HTTPException(status_code=409, detail="A completed order cannot be cancelled")

    if target == OrderStatus.completed:
        if user.role != UserRole.admin:
            raise HTTPException(status_code=403, detail="Only admins can mark an order as completed")
        if not await check_can_complete(order_id, session):
            raise HTTPException(
                status_code=409,
                detail="Cannot complete: not all logistics accepted or payment requests not fully paid",
            )

    if (
        current == OrderStatus.cancelled
        and target == OrderStatus.in_progress
        and user.role != UserRole.admin
    ):
        raise HTTPException(status_code=403, detail="Only admins can revert a cancelled order")

    if (
        current == OrderStatus.completed
        and target == OrderStatus.in_progress
        and user.role != UserRole.admin
    ):
        raise HTTPException(status_code=403, detail="Only admins can revert a completed order")

    order.status = target
    if target == OrderStatus.completed:
        order.completed_at = datetime.now(UTC)
        await snapshot_order_metrics(order_id, session)
    elif target == OrderStatus.in_progress and current == OrderStatus.completed:
        order.completed_at = None

    await log_action(
        session, user, "order.status_changed", "order", order.id, f"{current.value}→{target.value}"
    )
    await session.commit()
    await session.refresh(order)
    return _to_order_out(order, client_name, manager_name)


@router.post("/{order_id}/files", response_model=OrderOut)
async def add_order_file(
    order_id: int,
    body: OrderFileAdd,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    order = await _get_order_for_write(order_id, user, session)
    if len(order.file_keys) >= MAX_ORDER_FILES:
        raise HTTPException(status_code=422, detail=f"Maximum {MAX_ORDER_FILES} files per order")

    order.file_keys = [*order.file_keys, body.file_key]
    await session.commit()
    await session.refresh(order)

    row = (
        await session.execute(
            select(Client.full_name, User.full_name)
            .select_from(Order)
            .join(Client, Order.client_id == Client.id)
            .join(User, Order.manager_id == User.id)
            .where(Order.id == order_id)
        )
    ).first()
    client_name, manager_name = row
    return _to_order_out(order, client_name, manager_name)


@router.delete("/{order_id}/files/{file_key}", response_model=OrderOut)
async def remove_order_file(
    order_id: int,
    file_key: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    order = await _get_order_for_write(order_id, user, session)
    order.file_keys = [k for k in order.file_keys if k != file_key]
    await session.commit()
    await session.refresh(order)

    row = (
        await session.execute(
            select(Client.full_name, User.full_name)
            .select_from(Order)
            .join(Client, Order.client_id == Client.id)
            .join(User, Order.manager_id == User.id)
            .where(Order.id == order_id)
        )
    ).first()
    client_name, manager_name = row
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

    breakdown = await order_dependency_breakdown(session, order_id)
    dependency_count = sum(breakdown.values())
    if dependency_count > 0:
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"Order has {dependency_count} related record(s) and cannot be deleted",
                "breakdown": breakdown,
            },
        )

    await session.delete(order)
    await session.commit()
