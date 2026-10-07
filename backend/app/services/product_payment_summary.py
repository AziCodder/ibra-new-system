from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.models.payment_request import PaymentRequestItem
from app.models.product import Product

# Requests and payments are kept to the cent, while quantity * price can carry a
# fraction of one (2.5 kg at 10.01 = 25.025) — no payment could ever cover that.
PAID_TOLERANCE = Decimal("0.01")


@dataclass(frozen=True)
class UnpaidProduct:
    order_id: int
    name: str
    currency: str
    cost: Decimal
    paid: Decimal

    @property
    def missing(self) -> Decimal:
        return self.cost - self.paid


async def get_unpaid_products(session: AsyncSession, order_ids: list[int]) -> list[UnpaidProduct]:
    """Products of these orders whose cost isn't covered by payments, in their own currency.

    A product nobody ever raised a payment request for has no PaymentRequestItem
    row, so get_products_payment_totals omits it — and that omission means "not
    paid": exactly the forgotten payment this exists to catch (правки 2026-10-01 п.1).
    """
    if not order_ids:
        return []

    products = (
        await session.execute(
            select(Product.id, Product.order_id, Product.name, Product.currency, Product.quantity, Product.price)
            .where(Product.order_id.in_(order_ids))
            .order_by(Product.id)
        )
    ).all()
    totals = await get_products_payment_totals(session, [p.id for p in products])

    unpaid = []
    for product in products:
        _, paid = totals.get(product.id, (Decimal("0"), Decimal("0")))
        cost = product.quantity * product.price
        if cost - paid >= PAID_TOLERANCE:
            unpaid.append(UnpaidProduct(product.order_id, product.name, product.currency, cost, paid))
    return unpaid


async def get_products_payment_totals(
    session: AsyncSession, product_ids: list[int]
) -> dict[int, tuple[Decimal, Decimal]]:
    """Requested (exact) and paid (prorated) totals per product, in the product's currency.

    "Requested" is the exact sum of PaymentRequestItem.amount for the product.
    "Paid" has no direct per-product link — a payment settles a whole payment
    request, which can span multiple products — so it's prorated per request:
    paid_share = request_paid_total * (item_amount / request_total_amount).

    Both sides stay in the request's currency, which is the product's. A payment
    is made in its request's currency; `Payment.exchange_rate` is quoted towards
    the order's currency and feeds only the profit (see get_payment_request_paid).
    Multiplying it in would report a 5 400 CNY product paid at 13.4 as 72 360 paid.

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
                select(Payment.payment_request_id, func.sum(Payment.amount))
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
