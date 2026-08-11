from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.models.payment_request import PaymentRequest, PaymentRequestItem


async def get_payment_request_total(session: AsyncSession, payment_request_id: int) -> Decimal:
    return (
        await session.execute(
            select(func.coalesce(func.sum(PaymentRequestItem.amount), 0)).where(
                PaymentRequestItem.payment_request_id == payment_request_id
            )
        )
    ).scalar_one()


async def get_payment_request_paid(session: AsyncSession, payment_request_id: int) -> Decimal:
    """Sum of payments converted via each payment's manual exchange rate.

    exchange_rate is "how many payment-currency units make up 1 unit of the
    *payment request's* currency" — the currency the request's products are priced
    in, which is the direction the payment form asks for (`1 CNY = 11.5 RUB`), so
    the conversion divides. That currency is not necessarily the order's: a product
    may be priced in another one. profit.py performs the second hop (request
    currency -> order currency) using the rate stored on each product; see
    _calculate_purchases there.
    """
    rows = (
        await session.execute(
            select(Payment.amount, Payment.exchange_rate).where(Payment.payment_request_id == payment_request_id)
        )
    ).all()
    return sum((amount / rate for amount, rate in rows), start=Decimal("0"))


async def get_payment_request_paid_excluding(
    session: AsyncSession, payment_request_id: int, exclude_payment_id: int
) -> Decimal:
    """Same as get_payment_request_paid, minus one payment — used when editing/deleting that payment."""
    rows = (
        await session.execute(
            select(Payment.amount, Payment.exchange_rate).where(
                Payment.payment_request_id == payment_request_id, Payment.id != exclude_payment_id
            )
        )
    ).all()
    return sum((amount / rate for amount, rate in rows), start=Decimal("0"))


async def get_payment_request_remaining(session: AsyncSession, payment_request_id: int) -> Decimal:
    # Locks the payment request row until the caller's transaction commits, so two
    # concurrent payments against the same request can't both read the same
    # "remaining" value and jointly overpay it.
    await session.execute(
        select(PaymentRequest).where(PaymentRequest.id == payment_request_id).with_for_update()
    )
    total = await get_payment_request_total(session, payment_request_id)
    paid = await get_payment_request_paid(session, payment_request_id)
    return total - paid


async def get_payment_request_remaining_excluding(
    session: AsyncSession, payment_request_id: int, exclude_payment_id: int
) -> Decimal:
    """Remaining balance as if `exclude_payment_id` didn't exist — for re-validating an edit to that payment."""
    await session.execute(
        select(PaymentRequest).where(PaymentRequest.id == payment_request_id).with_for_update()
    )
    total = await get_payment_request_total(session, payment_request_id)
    paid = await get_payment_request_paid_excluding(session, payment_request_id, exclude_payment_id)
    return total - paid
