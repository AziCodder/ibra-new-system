from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.models.payment_request import PaymentRequest, PaymentRequestItem
from app.models.product import Product


class OrderPaymentTotals(NamedTuple):
    requested: Decimal
    paid: Decimal
    # The currency both sums are in; None when the order's requests are in different
    # currencies, so the sums mix units and only their ratio means anything.
    currency: str | None


async def get_orders_payment_totals(
    session: AsyncSession, order_ids: list[int]
) -> dict[int, OrderPaymentTotals]:
    """Requested (sum of payment request items) and paid (sum of payments) per order.

    Both sums are in the requests' own currency, which is that of their products —
    a payment is made in its request's currency, so no conversion is involved.
    `Payment.exchange_rate` is quoted towards the order's currency and feeds only
    the profit; multiplying it in would count 5 400 CNY paid as 72 360.

    An order with no payment requests at all is omitted from the result — callers should
    treat a missing key as "no payment request yet" rather than "fully paid".
    """
    if not order_ids:
        return {}

    requested_rows = (
        await session.execute(
            select(
                PaymentRequest.order_id,
                func.sum(PaymentRequestItem.amount),
                func.min(Product.currency),
                func.max(Product.currency),
            )
            .join(PaymentRequestItem, PaymentRequestItem.payment_request_id == PaymentRequest.id)
            .join(Product, Product.id == PaymentRequestItem.product_id)
            .where(PaymentRequest.order_id.in_(order_ids))
            .group_by(PaymentRequest.order_id)
        )
    ).all()

    paid_rows = (
        await session.execute(
            select(PaymentRequest.order_id, func.sum(Payment.amount))
            .join(Payment, Payment.payment_request_id == PaymentRequest.id)
            .where(PaymentRequest.order_id.in_(order_ids))
            .group_by(PaymentRequest.order_id)
        )
    ).all()

    paid_by_order = {order_id: paid for order_id, paid in paid_rows}
    return {
        order_id: OrderPaymentTotals(
            requested=requested,
            paid=paid_by_order.get(order_id, Decimal("0")),
            currency=lowest if lowest == highest else None,
        )
        for order_id, requested, lowest, highest in requested_rows
    }
