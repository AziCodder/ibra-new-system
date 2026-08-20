from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.models.payment_request import PaymentRequest, PaymentRequestItem
from app.models.product import Product


async def get_payment_request_total(session: AsyncSession, payment_request_id: int) -> Decimal:
    return (
        await session.execute(
            select(func.coalesce(func.sum(PaymentRequestItem.amount), 0)).where(
                PaymentRequestItem.payment_request_id == payment_request_id
            )
        )
    ).scalar_one()


async def get_payment_request_paid(session: AsyncSession, payment_request_id: int) -> Decimal:
    """Plain sum of the payments made against the request, in its own currency.

    A payment is always made in the request's currency — the operator states which
    part of the request they are settling, so no conversion is involved and the
    amounts add up directly. `Payment.exchange_rate` is the rate that money was
    bought at, quoted towards the *order's* currency; it feeds the order totals
    (see _calculate_purchases in profit.py) and deliberately plays no part here.
    Mixing it in would report 400 CNY paid at rate 12 as 4 800 CNY off a 1 000 CNY
    request and block the payment as an overpayment.
    """
    return (
        await session.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.payment_request_id == payment_request_id
            )
        )
    ).scalar_one()


async def get_payment_request_paid_excluding(
    session: AsyncSession, payment_request_id: int, exclude_payment_id: int
) -> Decimal:
    """Same as get_payment_request_paid, minus one payment — used when editing/deleting that payment."""
    return (
        await session.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.payment_request_id == payment_request_id, Payment.id != exclude_payment_id
            )
        )
    ).scalar_one()


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


async def get_payment_request_currency(session: AsyncSession, payment_request_id: int) -> str:
    """The currency a request is denominated in — that of the products on it.

    A payment against the request is always made in this currency, so it is read
    off the request rather than accepted from the client. A request always has at
    least one item when created through the API.
    """
    currency = (
        await session.execute(
            select(Product.currency)
            .join(PaymentRequestItem, PaymentRequestItem.product_id == Product.id)
            .where(PaymentRequestItem.payment_request_id == payment_request_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    return currency or ""
