from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.client import Client
from app.models.logistics import Logistics, LogisticsItem, LogisticsStatus
from app.models.logistics_comment import LogisticsComment
from app.models.product import Product
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.logistics import (
    LogisticsAccept,
    LogisticsCreate,
    LogisticsItemIn,
    LogisticsItemOut,
    LogisticsOut,
    LogisticsUpdate,
    NotifyLogisticsReceivedIn,
)
from app.schemas.logistics_comment import LogisticsCommentCreate, LogisticsCommentOut
from app.services.action_log import log_action
from app.services.logistics_items import ShipmentLine, get_logistics_items
from app.services.logistics_notifications import notify_shipment_sent
from app.services.logistics_validation import LogisticsValidationError, validate_logistics_items
from app.services.notifications import notify
from app.services.order_access import get_order_for_read as _get_order_for_read
from app.services.order_access import get_order_for_write as _get_order_for_write
from app.services.telegram_groups import get_client_send_targets

router = APIRouter(prefix="/api/orders/{order_id}/logistics", tags=["logistics"])


async def _check_products_in_order(order_id: int, product_ids: list[int], session: AsyncSession) -> None:
    found = {
        row[0]
        for row in (
            await session.execute(
                select(Product.id).where(Product.id.in_(product_ids), Product.order_id == order_id)
            )
        ).all()
    }
    missing = set(product_ids) - found
    if missing:
        raise HTTPException(status_code=422, detail=f"Products {sorted(missing)} do not belong to this order")


async def _replace_items(logistics_id: int, items: list[LogisticsItemIn], session: AsyncSession) -> None:
    await session.execute(delete(LogisticsItem).where(LogisticsItem.logistics_id == logistics_id))
    for item in items:
        session.add(
            LogisticsItem(logistics_id=logistics_id, product_id=item.product_id, quantity=item.quantity)
        )


async def _get_logistics_or_404(order_id: int, logistics_id: int, session: AsyncSession) -> Logistics:
    result = await session.execute(
        select(Logistics).where(Logistics.id == logistics_id, Logistics.order_id == order_id)
    )
    logistics = result.scalar_one_or_none()
    if not logistics:
        raise HTTPException(status_code=404, detail="Logistics record not found")
    return logistics


def _check_manager_can_edit(logistics: Logistics, user: User) -> None:
    """Managers may only edit shipments still in transit; admins may edit any status."""
    if user.role == UserRole.manager and logistics.status != LogisticsStatus.in_transit:
        raise HTTPException(status_code=403, detail="Only shipments in transit can be edited by a manager")


def _check_fields_frozen(logistics: Logistics, updates: dict) -> None:
    """Once accepted or cancelled, only a status transition may go through PATCH —
    every other field is frozen for every role (including admin) until the shipment
    is returned to in-transit via /unaccept.
    """
    if logistics.status in (LogisticsStatus.accepted, LogisticsStatus.cancelled):
        frozen_fields = set(updates) - {"status"}
        if frozen_fields:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Shipment is {logistics.status.value}; only its status can change via PATCH "
                    f"(rejected fields: {', '.join(sorted(frozen_fields))})"
                ),
            )


def _check_deletable(logistics: Logistics) -> None:
    """Deletion is restricted to in-transit shipments for every role (no admin exception)."""
    if logistics.status != LogisticsStatus.in_transit:
        raise HTTPException(status_code=403, detail="Only shipments in transit can be deleted")


def _require_admin(user: User) -> None:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can accept or unaccept a shipment")


def _build_logistics_out(
    logistics: Logistics, creator_name: str, lines: list[ShipmentLine]
) -> LogisticsOut:
    return LogisticsOut(
        id=logistics.id,
        order_id=logistics.order_id,
        items=[
            LogisticsItemOut(product_id=line.product_id, product_name=line.product_name, quantity=line.quantity)
            for line in lines
        ],
        created_by_id=logistics.created_by_id,
        created_by_name=creator_name,
        total_quantity=sum((line.quantity for line in lines), start=Decimal("0")),
        tracking=logistics.tracking,
        ship_date=logistics.ship_date,
        invoice_file_key=logistics.invoice_file_key,
        details=logistics.details,
        status=logistics.status,
        received_date=logistics.received_date,
        expense_amount=logistics.expense_amount,
        currency=logistics.currency,
        exchange_rate=logistics.exchange_rate,
        acceptance_note=logistics.acceptance_note,
        created_at=logistics.created_at,
    )


async def _to_logistics_out(logistics: Logistics, session: AsyncSession) -> LogisticsOut:
    creator_name = (
        await session.execute(select(User.full_name).where(User.id == logistics.created_by_id))
    ).scalar_one()
    items = (await get_logistics_items(session, [logistics.id])).get(logistics.id, [])
    return _build_logistics_out(logistics, creator_name, items)


@router.get("/", response_model=list[LogisticsOut])
async def list_logistics(
    order_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_read(order_id, user, session)

    rows = (
        await session.execute(
            select(Logistics, User.full_name)
            .join(User, Logistics.created_by_id == User.id)
            .where(Logistics.order_id == order_id)
            .order_by(Logistics.created_at)
        )
    ).all()
    items_by_logistics = await get_logistics_items(session, [logistics.id for logistics, _ in rows])
    return [
        _build_logistics_out(logistics, creator_name, items_by_logistics.get(logistics.id, []))
        for logistics, creator_name in rows
    ]


@router.get("/{logistics_id}", response_model=LogisticsOut)
async def get_logistics(
    order_id: int,
    logistics_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_read(order_id, user, session)
    logistics = await _get_logistics_or_404(order_id, logistics_id, session)
    return await _to_logistics_out(logistics, session)


@router.post("/", response_model=LogisticsOut, status_code=201)
async def create_logistics(
    order_id: int,
    body: LogisticsCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_write(order_id, user, session)
    await _check_products_in_order(order_id, [item.product_id for item in body.items], session)

    if body.status == LogisticsStatus.accepted:
        _require_admin(user)

    try:
        await validate_logistics_items(session, [(item.product_id, item.quantity) for item in body.items])
    except LogisticsValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None

    logistics = Logistics(
        order_id=order_id,
        created_by_id=user.id,
        tracking=body.tracking,
        ship_date=body.ship_date,
        invoice_file_key=body.invoice_file_key,
        details=body.details,
        status=body.status,
        received_date=body.received_date,
        expense_amount=body.expense_amount,
        currency=body.currency,
        exchange_rate=body.exchange_rate,
        acceptance_note=body.acceptance_note,
    )
    session.add(logistics)
    await session.flush()
    await _replace_items(logistics.id, body.items, session)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Tracking number already exists in the system")
    await session.refresh(logistics)
    await notify_shipment_sent(logistics, session)
    return await _to_logistics_out(logistics, session)


@router.patch("/{logistics_id}", response_model=LogisticsOut)
async def update_logistics(
    order_id: int,
    logistics_id: int,
    body: LogisticsUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_write(order_id, user, session)
    logistics = await _get_logistics_or_404(order_id, logistics_id, session)
    _check_manager_can_edit(logistics, user)

    updates = body.model_dump(exclude_unset=True)
    _check_fields_frozen(logistics, updates)

    if updates.get("status") == LogisticsStatus.accepted:
        raise HTTPException(status_code=422, detail="Use POST /accept to accept a shipment")

    # Lines are stored in their own table, so they never go through setattr below.
    new_items = body.items if "items" in updates else None
    updates.pop("items", None)

    if new_items is not None:
        await _check_products_in_order(order_id, [item.product_id for item in new_items], session)
        try:
            await validate_logistics_items(
                session,
                [(item.product_id, item.quantity) for item in new_items],
                exclude_logistics_id=logistics.id,
            )
        except LogisticsValidationError as e:
            raise HTTPException(status_code=422, detail=str(e)) from None
        await _replace_items(logistics.id, new_items, session)

    for field, value in updates.items():
        setattr(logistics, field, value)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Tracking number already exists in the system")
    await session.refresh(logistics)
    return await _to_logistics_out(logistics, session)


@router.delete("/{logistics_id}", status_code=204)
async def delete_logistics(
    order_id: int,
    logistics_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_write(order_id, user, session)
    logistics = await _get_logistics_or_404(order_id, logistics_id, session)
    _check_deletable(logistics)

    await session.delete(logistics)
    await session.commit()


@router.post("/{logistics_id}/accept", response_model=LogisticsOut)
async def accept_logistics(
    order_id: int,
    logistics_id: int,
    body: LogisticsAccept,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_write(order_id, user, session)
    _require_admin(user)
    logistics = await _get_logistics_or_404(order_id, logistics_id, session)

    if logistics.status != LogisticsStatus.in_transit:
        raise HTTPException(status_code=409, detail="Only shipments in transit can be accepted")

    logistics.status = LogisticsStatus.accepted
    logistics.received_date = body.received_date
    logistics.expense_amount = body.expense_amount
    logistics.currency = body.currency
    logistics.exchange_rate = body.exchange_rate
    logistics.acceptance_note = body.note

    await log_action(
        session, user, "logistics.accepted", "logistics", logistics.id,
        f"order {order_id}, expense {body.expense_amount} {body.currency}",
    )
    await session.commit()
    await session.refresh(logistics)
    return await _to_logistics_out(logistics, session)


@router.post("/{logistics_id}/unaccept", response_model=LogisticsOut)
async def unaccept_logistics(
    order_id: int,
    logistics_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_write(order_id, user, session)
    _require_admin(user)
    logistics = await _get_logistics_or_404(order_id, logistics_id, session)

    if logistics.status != LogisticsStatus.accepted:
        raise HTTPException(status_code=409, detail="Only accepted shipments can be unaccepted")

    logistics.status = LogisticsStatus.in_transit
    logistics.received_date = None
    logistics.expense_amount = None
    logistics.currency = None
    logistics.exchange_rate = None
    logistics.acceptance_note = None

    await session.commit()
    await session.refresh(logistics)
    return await _to_logistics_out(logistics, session)


@router.get("/{logistics_id}/comments", response_model=list[LogisticsCommentOut])
async def list_logistics_comments(
    order_id: int,
    logistics_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_read(order_id, user, session)
    await _get_logistics_or_404(order_id, logistics_id, session)

    result = await session.execute(
        select(LogisticsComment, User.full_name)
        .join(User, LogisticsComment.author_id == User.id)
        .where(LogisticsComment.logistics_id == logistics_id)
        .order_by(LogisticsComment.created_at)
    )
    return [
        LogisticsCommentOut(
            id=comment.id,
            logistics_id=comment.logistics_id,
            author_id=comment.author_id,
            author_name=author_name,
            text=comment.text,
            created_at=comment.created_at,
        )
        for comment, author_name in result.all()
    ]


@router.post("/{logistics_id}/comments", response_model=LogisticsCommentOut, status_code=201)
async def create_logistics_comment(
    order_id: int,
    logistics_id: int,
    body: LogisticsCommentCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Comments are addable by every role on any status — observer included, per ТЗ §9."""
    await _get_order_for_read(order_id, user, session)
    await _get_logistics_or_404(order_id, logistics_id, session)

    comment = LogisticsComment(logistics_id=logistics_id, author_id=user.id, text=body.text)
    session.add(comment)
    await session.commit()
    await session.refresh(comment)
    return LogisticsCommentOut(
        id=comment.id,
        logistics_id=comment.logistics_id,
        author_id=comment.author_id,
        author_name=user.full_name,
        text=comment.text,
        created_at=comment.created_at,
    )


@router.post("/{logistics_id}/notify-received", status_code=204)
async def notify_logistics_received(
    order_id: int,
    logistics_id: int,
    body: NotifyLogisticsReceivedIn | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """«Отправить уведомление о получении».

    0 linked groups -> private chat (unchanged legacy behavior).
    1 linked group  -> auto-sent there, no picker.
    2+ linked groups -> caller must pass group_ids; if omitted, 409 with
    available groups so the frontend can render a picker and retry.

    Deliberately uses the read-level guard, not _get_order_for_write: sending this
    notice doesn't mutate any order data (no effect on the profit snapshot), so
    it stays available even after the order is completed — only the observer
    restriction applies.
    """
    if user.role == UserRole.observer:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    order = await _get_order_for_read(order_id, user, session)
    logistics = await _get_logistics_or_404(order_id, logistics_id, session)

    client = (await session.execute(select(Client).where(Client.id == order.client_id))).scalar_one()
    message = f"Товар по заказу {order.number} получен. Трекинг: {logistics.tracking or '—'}."

    targets = await get_client_send_targets(client, session)
    if not targets:
        notify(client.telegram_chat_id, message)
        return

    group_ids = body.group_ids if body is not None else None
    if group_ids is None:
        if len(targets) > 1:
            raise HTTPException(status_code=409, detail={"available_groups": targets})
        notify(targets[0]["chat_id"], message)
        return

    chosen = [t for t in targets if t["group_id"] in group_ids]
    if not chosen:
        raise HTTPException(status_code=422, detail="No valid group_ids for this client")
    for t in chosen:
        notify(t["chat_id"], message)
