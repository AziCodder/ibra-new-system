from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.models.payment_request import PaymentRequestItem


async def get_products_payment_totals(
    session: AsyncSession, product_ids: list[int]
) -> dict[int, tuple[Decimal, Decimal]]:
    """Requested (exact) and paid (prorated) totals per product.

    "Requested" is the exact sum of PaymentRequestItem.amount for the product.
    "Paid" has no direct per-product link — a payment settles a whole payment
    request, which can span multiple products — so it's prorated per request:
    paid_share = request_paid_total * (item_amount / request_total_amount).
    A product with no payment-request items at all is omitted from the result
    (mirrors order_payment_summary.get_orders_payment_totals's convention).
    """
    if not product_ids:
        return {}

    requested_rows = (
        await session.execute(
            select(PaymentRequestItem.product_id, func.sum(PaymentRequestItem.amount))
            .where(PaymentRequestItem.product_id.in_(product_ids))
            .group_by(PaymentRequestItem.product_id)
        )
    ).all()
    requested_by_product = dict(requested_rows)
    if not requested_by_product:
        return {}

    item_rows = (
        await session.execute(
            select(PaymentRequestItem.product_id, PaymentRequestItem.payment_request_id, PaymentRequestItem.amount).where(
                PaymentRequestItem.product_id.in_(product_ids)
            )
        )
    ).all()
    request_ids = {request_id for _, request_id, _ in item_rows}

    request_total_by_id = dict(
        (
            await session.execute(
                select(PaymentRequestItem.payment_request_id, func.sum(PaymentRequestItem.amount))
                .where(PaymentRequestItem.payment_request_id.in_(request_ids))
                .group_by(PaymentRequestItem.payment_request_id)
            )
        ).all()
    )
    request_paid_by_id = dict(
        (
            await session.execute(
                select(Payment.payment_request_id, func.sum(Payment.amount * Payment.exchange_rate))
                .where(Payment.payment_request_id.in_(request_ids))
                .group_by(Payment.payment_request_id)
            )
        ).all()
    )

    paid_by_product: dict[int, Decimal] = {}
    for product_id, request_id, item_amount in item_rows:
        request_total = request_total_by_id.get(request_id) or Decimal("0")
        request_paid = request_paid_by_id.get(request_id) or Decimal("0")
        share = (request_paid * item_amount / request_total) if request_total else Decimal("0")
        paid_by_product[product_id] = paid_by_product.get(product_id, Decimal("0")) + share

    return {
        product_id: (requested, paid_by_product.get(product_id, Decimal("0")))
        for product_id, requested in requested_by_product.items()
    }
