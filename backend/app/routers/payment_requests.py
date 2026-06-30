from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.client import Client
from app.models.order import Order
from app.models.payment_request import PaymentRequest, PaymentRequestItem
from app.models.product import Product
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.payment_request import (
    PaymentRequestCreate,
    PaymentRequestItemOut,
    PaymentRequestOut,
    PaymentRequestUpdate,
)
from app.services.notifications import notify
from app.services.payment_remaining import get_payment_request_paid
from app.services.payment_request_dependencies import count_payment_request_dependencies
from app.services.payment_request_validation import PaymentRequestValidationError, validate_payment_request_items

router = APIRouter(prefix="/api/orders/{order_id}/payment-requests", tags=["payment_requests"])


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


async def _validate_items_belong_to_order(order_id: int, product_ids: list[int], session: AsyncSession) -> None:
    result = await session.execute(select(Product.id).where(Product.id.in_(product_ids), Product.order_id == order_id))
    found_ids = {row[0] for row in result.all()}
    missing = set(product_ids) - found_ids
    if missing:
        raise HTTPException(status_code=422, detail=f"Products {sorted(missing)} do not belong to this order")


async def _to_payment_request_out(request: PaymentRequest, session: AsyncSession) -> PaymentRequestOut:
    creator = (await session.execute(select(User).where(User.id == request.created_by_id))).scalar_one()

    rows = (
        await session.execute(
            select(PaymentRequestItem, Product.name, Product.currency)
            .join(Product, PaymentRequestItem.product_id == Product.id)
            .where(PaymentRequestItem.payment_request_id == request.id)
        )
    ).all()

    items = [
        PaymentRequestItemOut(id=item.id, product_id=item.product_id, product_name=product_name, amount=item.amount)
        for item, product_name, _ in rows
    ]
    currency = rows[0][2] if rows else ""
    total_amount = sum((item.amount for item in items), start=Decimal("0"))
    paid_amount = await get_payment_request_paid(session, request.id)

    return PaymentRequestOut(
        id=request.id,
        order_id=request.order_id,
        created_by_id=request.created_by_id,
        created_by_name=creator.full_name,
        requisites=request.requisites,
        details=request.details,
        priority=request.priority,
        file_keys=request.file_keys,
        currency=currency,
        total_amount=total_amount,
        paid_amount=paid_amount,
        remaining_amount=total_amount - paid_amount,
        items=items,
        created_at=request.created_at,
    )


@router.get("/", response_model=list[PaymentRequestOut])
async def list_payment_requests(
    order_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_read(order_id, user, session)

    result = await session.execute(
        select(PaymentRequest).where(PaymentRequest.order_id == order_id).order_by(PaymentRequest.created_at)
    )
    return [await _to_payment_request_out(request, session) for request in result.scalars().all()]


@router.get("/{request_id}", response_model=PaymentRequestOut)
async def get_payment_request(
    order_id: int,
    request_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_read(order_id, user, session)

    result = await session.execute(
        select(PaymentRequest).where(PaymentRequest.id == request_id, PaymentRequest.order_id == order_id)
    )
    request = result.scalar_one_or_none()
    if not request:
        raise HTTPException(status_code=404, detail="Payment request not found")
    return await _to_payment_request_out(request, session)


@router.post("/", response_model=PaymentRequestOut, status_code=201)
async def create_payment_request(
    order_id: int,
    body: PaymentRequestCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    order = await _get_order_for_write(order_id, user, session)

    product_ids = [item.product_id for item in body.items]
    await _validate_items_belong_to_order(order_id, product_ids, session)

    try:
        await validate_payment_request_items(session, [(item.product_id, item.amount) for item in body.items])
    except PaymentRequestValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None

    request = PaymentRequest(
        order_id=order_id,
        created_by_id=user.id,
        requisites=body.requisites,
        details=body.details,
        priority=body.priority,
        file_keys=body.file_keys,
    )
    session.add(request)
    await session.flush()

    for item in body.items:
        session.add(PaymentRequestItem(payment_request_id=request.id, product_id=item.product_id, amount=item.amount))

    await session.commit()
    await session.refresh(request)
    out = await _to_payment_request_out(request, session)

    client = (await session.execute(select(Client).where(Client.id == order.client_id))).scalar_one()
    notify(
        client.telegram_group_link,
        f"По заказу {order.number} выставлен запрос на оплату на сумму {out.total_amount} {out.currency}. "
        f"Детали: {request.details or '—'}. Реквизиты: {request.requisites or '—'}. "
        f"Ссылка на заказ: /orders/{order.id}",
    )

    return out


@router.patch("/{request_id}", response_model=PaymentRequestOut)
async def update_payment_request(
    order_id: int,
    request_id: int,
    body: PaymentRequestUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_write(order_id, user, session)

    result = await session.execute(
        select(PaymentRequest).where(PaymentRequest.id == request_id, PaymentRequest.order_id == order_id)
    )
    request = result.scalar_one_or_none()
    if not request:
        raise HTTPException(status_code=404, detail="Payment request not found")

    updates = body.model_dump(exclude_unset=True, exclude={"items"})

    if body.items is not None:
        product_ids = [item.product_id for item in body.items]
        await _validate_items_belong_to_order(order_id, product_ids, session)
        try:
            await validate_payment_request_items(
                session,
                [(item.product_id, item.amount) for item in body.items],
                exclude_request_id=request.id,
            )
        except PaymentRequestValidationError as e:
            raise HTTPException(status_code=422, detail=str(e)) from None

        await session.execute(delete(PaymentRequestItem).where(PaymentRequestItem.payment_request_id == request.id))
        for item in body.items:
            session.add(PaymentRequestItem(payment_request_id=request.id, product_id=item.product_id, amount=item.amount))

    for field, value in updates.items():
        setattr(request, field, value)

    await session.commit()
    await session.refresh(request)
    return await _to_payment_request_out(request, session)


@router.delete("/{request_id}", status_code=204)
async def delete_payment_request(
    order_id: int,
    request_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_write(order_id, user, session)

    result = await session.execute(
        select(PaymentRequest).where(PaymentRequest.id == request_id, PaymentRequest.order_id == order_id)
    )
    request = result.scalar_one_or_none()
    if not request:
        raise HTTPException(status_code=404, detail="Payment request not found")

    dependency_count = await count_payment_request_dependencies(session, request_id)
    if dependency_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Payment request has {dependency_count} related record(s) and cannot be deleted",
        )

    await session.delete(request)
    await session.commit()
