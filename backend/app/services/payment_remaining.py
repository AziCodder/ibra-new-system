from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.models.payment_request import PaymentRequestItem


async def get_payment_request_total(session: AsyncSession, payment_request_id: int) -> Decimal:
    return (
        await session.execute(
            select(func.coalesce(func.sum(PaymentRequestItem.amount), 0)).where(
                PaymentRequestItem.payment_request_id == payment_request_id
            )
        )
    ).scalar_one()


async def get_payment_request_paid(session: AsyncSession, payment_request_id: int) -> Decimal:
    """Sum of payments converted into the request's currency via each payment's manual exchange rate."""
    rows = (
        await session.execute(
            select(Payment.amount, Payment.exchange_rate).where(Payment.payment_request_id == payment_request_id)
        )
    ).all()
    return sum((amount * rate for amount, rate in rows), start=Decimal("0"))


async def get_payment_request_remaining(session: AsyncSession, payment_request_id: int) -> Decimal:
    total = await get_payment_request_total(session, payment_request_id)
    paid = await get_payment_request_paid(session, payment_request_id)
    return total - paid
