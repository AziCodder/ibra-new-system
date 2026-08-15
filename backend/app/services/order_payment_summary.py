from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.models.payment_request import PaymentRequest, PaymentRequestItem


async def get_orders_payment_totals(
    session: AsyncSession, order_ids: list[int]
) -> dict[int, tuple[Decimal, Decimal]]:
    """Requested (sum of payment request items) and paid (sum of payments, converted) per order.

    Payments convert into the request's currency via `amount * exchange_rate` —
    the rate is stored as "request-currency units per 1 payment-currency unit".

    An order with no payment requests at all is omitted from the result — callers should
    treat a missing key as "no payment request yet" rather than "fully paid".
    """
    if not order_ids:
        return {}

    requested_rows = (
        await session.execute(
            select(PaymentRequest.order_id, func.sum(PaymentRequestItem.amount))
            .join(PaymentRequestItem, PaymentRequestItem.payment_request_id == PaymentRequest.id)
            .where(PaymentRequest.order_id.in_(order_ids))
            .group_by(PaymentRequest.order_id)
        )
    ).all()

    paid_rows = (
        await session.execute(
            select(PaymentRequest.order_id, func.sum(Payment.amount * Payment.exchange_rate))
            .join(Payment, Payment.payment_request_id == PaymentRequest.id)
            .where(PaymentRequest.order_id.in_(order_ids))
            .group_by(PaymentRequest.order_id)
        )
    ).all()

    paid_by_order = {order_id: paid for order_id, paid in paid_rows}
    return {
        order_id: (requested, paid_by_order.get(order_id, Decimal("0")))
        for order_id, requested in requested_rows
    }
