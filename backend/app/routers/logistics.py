from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.logistics import Logistics, LogisticsStatus
from app.models.order import Order
from app.models.product import Product
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.logistics import LogisticsAccept, LogisticsCreate, LogisticsOut, LogisticsUpdate
from app.services.logistics_validation import LogisticsValidationError, validate_logistics_quantity

router = APIRouter(prefix="/api/orders/{order_id}/logistics", tags=["logistics"])


async def _get_order_for_read(order_id: int, user: User, session: AsyncSession) -> Order:
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if user.role == UserRole.manager and order.manager_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


async def _get_order_for_write(order_id: int, user: User, session: AsyncSession) -> Order:
    if user.role == UserRole.observer:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return await _get_order_for_read(order_id, user, session)


async def _get_product_in_order(order_id: int, product_id: int, session: AsyncSession) -> Product:
    result = await session.execute(select(Product).where(Product.id == product_id, Product.order_id == order_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=422, detail=f"Product {product_id} does not belong to this order")
    return product


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


def _check_deletable(logistics: Logistics) -> None:
    """Deletion is restricted to in-transit shipments for every role (no admin exception)."""
    if logistics.status != LogisticsStatus.in_transit:
        raise HTTPException(status_code=403, detail="Only shipments in transit can be deleted")


def _require_admin(user: User) -> None:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can accept or unaccept a shipment")


async def _to_logistics_out(logistics: Logistics, session: AsyncSession) -> LogisticsOut:
    product = (await session.execute(select(Product).where(Product.id == logistics.product_id))).scalar_one()
    creator = (await session.execute(select(User).where(User.id == logistics.created_by_id))).scalar_one()

    return LogisticsOut(
        id=logistics.id,
        order_id=logistics.order_id,
        product_id=logistics.product_id,
        product_name=product.name,
        created_by_id=logistics.created_by_id,
        created_by_name=creator.full_name,
        quantity=logistics.quantity,
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


@router.get("/", response_model=list[LogisticsOut])
async def list_logistics(
    order_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_read(order_id, user, session)

    result = await session.execute(
        select(Logistics).where(Logistics.order_id == order_id).order_by(Logistics.created_at)
    )
    return [await _to_logistics_out(logistics, session) for logistics in result.scalars().all()]


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
    await _get_product_in_order(order_id, body.product_id, session)

    if body.status == LogisticsStatus.accepted:
        _require_admin(user)

    try:
        await validate_logistics_quantity(session, body.product_id, body.quantity)
    except LogisticsValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None

    logistics = Logistics(
        order_id=order_id,
        product_id=body.product_id,
        created_by_id=user.id,
        quantity=body.quantity,
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
    await session.commit()
    await session.refresh(logistics)
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

    if updates.get("status") == LogisticsStatus.accepted:
        raise HTTPException(status_code=422, detail="Use POST /accept to accept a shipment")

    if "quantity" in updates:
        try:
            await validate_logistics_quantity(
                session, logistics.product_id, updates["quantity"], exclude_logistics_id=logistics.id
            )
        except LogisticsValidationError as e:
            raise HTTPException(status_code=422, detail=str(e)) from None

    for field, value in updates.items():
        setattr(logistics, field, value)

    await session.commit()
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
