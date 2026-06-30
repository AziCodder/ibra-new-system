from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.order import Order
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.payment import PaymentCreate, PaymentOut

router = APIRouter(prefix="/api/orders/{order_id}/payment-requests/{request_id}/payments", tags=["payments"])


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


async def _get_payment_request_or_404(order_id: int, request_id: int, session: AsyncSession) -> PaymentRequest:
    result = await session.execute(
        select(PaymentRequest).where(PaymentRequest.id == request_id, PaymentRequest.order_id == order_id)
    )
    request = result.scalar_one_or_none()
    if not request:
        raise HTTPException(status_code=404, detail="Payment request not found")
    return request


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
            .order_by(Payment.created_at)
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

    payment = Payment(
        payment_request_id=request_id,
        author_id=user.id,
        amount=body.amount,
        currency=body.currency,
        exchange_rate=body.exchange_rate,
        file_key=body.file_key,
        note=body.note,
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return _to_payment_out(payment, user.full_name)
