from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.payment import PaymentCreate, PaymentOut, PaymentUpdate
from app.services.order_access import get_order_for_read as _get_order_for_read
from app.services.order_access import get_order_for_write as _get_order_for_write
from app.services.payment_notifications import notify_payment_recorded
from app.services.payment_remaining import (
    get_payment_request_currency,
    get_payment_request_remaining,
    get_payment_request_remaining_excluding,
)

router = APIRouter(prefix="/api/orders/{order_id}/payment-requests/{request_id}/payments", tags=["payments"])


async def _get_payment_request_or_404(order_id: int, request_id: int, session: AsyncSession) -> PaymentRequest:
    result = await session.execute(
        select(PaymentRequest).where(PaymentRequest.id == request_id, PaymentRequest.order_id == order_id)
    )
    request = result.scalar_one_or_none()
    if not request:
        raise HTTPException(status_code=404, detail="Payment request not found")
    return request


async def _get_payment_or_404(request_id: int, payment_id: int, session: AsyncSession) -> Payment:
    result = await session.execute(
        select(Payment).where(Payment.id == payment_id, Payment.payment_request_id == request_id)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


def _to_payment_out(payment: Payment, author_name: str) -> PaymentOut:
    return PaymentOut(
        id=payment.id,
        payment_request_id=payment.payment_request_id,
        author_id=payment.author_id,
        author_name=author_name,
        amount=payment.amount,
        currency=payment.currency,
        exchange_rate=payment.exchange_rate,
        file_key=payment.file_key,
        note=payment.note,
        paid_at=payment.paid_at,
        created_at=payment.created_at,
    )


@router.get("/", response_model=list[PaymentOut])
async def list_payments(
    order_id: int,
    request_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_read(order_id, user, session)
    await _get_payment_request_or_404(order_id, request_id, session)

    rows = (
        await session.execute(
            select(Payment, User.full_name)
            .join(User, Payment.author_id == User.id)
            .where(Payment.payment_request_id == request_id)
            .order_by(Payment.paid_at)
        )
    ).all()
    return [_to_payment_out(payment, author_name) for payment, author_name in rows]


@router.post("/", response_model=PaymentOut, status_code=201)
async def create_payment(
    order_id: int,
    request_id: int,
    body: PaymentCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_write(order_id, user, session)
    await _get_payment_request_or_404(order_id, request_id, session)

    # Both sides are in the request's own currency — the payment is made in it,
    # so the amount needs no conversion before the comparison.
    remaining = await get_payment_request_remaining(session, request_id)
    if body.amount > remaining:
        raise HTTPException(
            status_code=422,
            detail=f"Payment amount ({body.amount}) exceeds remaining balance ({remaining})",
        )

    payment = Payment(
        payment_request_id=request_id,
        author_id=user.id,
        amount=body.amount,
        currency=await get_payment_request_currency(session, request_id),
        exchange_rate=body.exchange_rate,
        file_key=body.file_key,
        note=body.note,
        paid_at=body.paid_at or datetime.now(UTC),
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    await notify_payment_recorded(payment, session)
    return _to_payment_out(payment, user.full_name)


@router.patch("/{payment_id}", response_model=PaymentOut)
async def update_payment(
    order_id: int,
    request_id: int,
    payment_id: int,
    body: PaymentUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_write(order_id, user, session)
    await _get_payment_request_or_404(order_id, request_id, session)
    payment = await _get_payment_or_404(request_id, payment_id, session)

    remaining = await get_payment_request_remaining_excluding(session, request_id, payment_id)
    if body.amount > remaining:
        raise HTTPException(
            status_code=422,
            detail=f"Payment amount ({body.amount}) exceeds remaining balance ({remaining})",
        )

    payment.amount = body.amount
    payment.currency = await get_payment_request_currency(session, request_id)
    payment.exchange_rate = body.exchange_rate
    payment.file_key = body.file_key
    payment.note = body.note
    payment.paid_at = body.paid_at

    await session.commit()
    await session.refresh(payment)

    author_name = (await session.execute(select(User.full_name).where(User.id == payment.author_id))).scalar_one()
    return _to_payment_out(payment, author_name)


@router.delete("/{payment_id}", status_code=204)
async def delete_payment(
    order_id: int,
    request_id: int,
    payment_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_write(order_id, user, session)
    await _get_payment_request_or_404(order_id, request_id, session)
    payment = await _get_payment_or_404(request_id, payment_id, session)

    await session.delete(payment)
    await session.commit()
