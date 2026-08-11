from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger_entry import LedgerEntry, LedgerEntryType
from app.models.logistics import Logistics, LogisticsItem, LogisticsStatus
from app.models.order import Order
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest, PaymentRequestItem
from app.models.product import Product


@dataclass
class ProfitBreakdown:
    income: Decimal
    purchases: Decimal
    logistics: Decimal
    other_expenses: Decimal
    profit: Decimal
    currency: str
    is_ready: bool


async def _check_readiness(order_id: int, session: AsyncSession) -> bool:
    """Return True only when the order is fully received and nothing is still in transit.

    Conditions (ТЗ §11):
    1. The order has at least one product.
    2. No logistics entries are in_transit status (everything has been settled).
    3. For every product the sum of accepted logistics quantities >= product quantity.
    """
    has_products = (
        await session.execute(select(Product.id).where(Product.order_id == order_id).limit(1))
    ).scalar_one_or_none()
    if has_products is None:
        return False

    in_transit = (
        await session.execute(
            select(Logistics.id)
            .where(Logistics.order_id == order_id, Logistics.status == LogisticsStatus.in_transit)
            .limit(1)
        )
    ).scalar_one_or_none()
    if in_transit is not None:
        return False

    # Correlated subquery: accepted shipped quantity per product
    shipped_sub = (
        select(func.coalesce(func.sum(LogisticsItem.quantity), Decimal("0")))
        .join(Logistics, LogisticsItem.logistics_id == Logistics.id)
        .where(LogisticsItem.product_id == Product.id, Logistics.status == LogisticsStatus.accepted)
        .correlate(Product)
        .scalar_subquery()
    )
    undershipped = (
        await session.execute(
            select(Product.id)
            .where(Product.order_id == order_id, shipped_sub < Product.quantity)
            .limit(1)
        )
    ).scalar_one_or_none()
    return undershipped is None


async def _calculate_purchases(order_id: int, session: AsyncSession) -> Decimal:
    """Total actually paid for the order's products, in the order's currency.

    Every rate in the system reads "how many units of the operation's currency
    make up 1 unit of the target currency" (`1 CNY = 11.5 RUB` -> 11.5), so a
    conversion is always `amount / exchange_rate`.

    Two conversions stack, because two different currencies can be in play:

    1. `Payment.exchange_rate` converts a payment into the *payment request's*
       currency — the currency the products on that request are priced in. This
       is what the remaining-balance check in payment_remaining.py works in, and
       what the payment form asks the user for.
    2. The request's currency is then converted into the *order's* currency using
       the exchange rate stored on each product.

    A request may in principle mix products carrying different rates, so step 2
    uses the request's amount-weighted average of the *inverse* rates — averaging
    1/rate rather than rate is what keeps a division-based conversion additive.
    That is exact, not an approximation: a payment covers a request's items in
    proportion to their amounts (the same allocation product_payment_summary.py
    uses). For the common case — every product priced in the order's currency —
    every rate is 1 and this reduces to the plain sum of payments.
    """
    paid_per_request = (
        await session.execute(
            select(
                PaymentRequest.id,
                func.coalesce(func.sum(Payment.amount / Payment.exchange_rate), Decimal("0")),
            )
            .outerjoin(Payment, Payment.payment_request_id == PaymentRequest.id)
            .where(PaymentRequest.order_id == order_id)
            .group_by(PaymentRequest.id)
        )
    ).all()

    rate_per_request = {
        request_id: (weighted, total)
        for request_id, weighted, total in (
            await session.execute(
                select(
                    PaymentRequestItem.payment_request_id,
                    func.sum(PaymentRequestItem.amount / Product.exchange_rate),
                    func.sum(PaymentRequestItem.amount),
                )
                .join(Product, PaymentRequestItem.product_id == Product.id)
                .join(PaymentRequest, PaymentRequestItem.payment_request_id == PaymentRequest.id)
                .where(PaymentRequest.order_id == order_id)
                .group_by(PaymentRequestItem.payment_request_id)
            )
        ).all()
    }

    purchases = Decimal("0")
    for request_id, paid in paid_per_request:
        weighted, total = rate_per_request.get(request_id, (None, None))
        # `weighted` already sums amount/rate, so the ratio below is the average
        # *inverse* rate — multiply by it instead of dividing. An itemless request
        # can't exist through the API; treat it as rate 1 rather than dropping
        # payments that were recorded against it.
        inverse_rate = weighted / total if total else Decimal("1")
        purchases += paid * inverse_rate
    return purchases


async def calculate_profit(order_id: int, session: AsyncSession) -> ProfitBreakdown:
    """Calculate profit for an order in its currency.

    Formula: Income − Purchases − Logistics − Other expenses = Profit

    Ledger entries and logistics expenses convert to the order currency via
    `amount / exchange_rate`, where the rate is stored as "operation-currency
    units per 1 order-currency unit" — the direction the forms ask for
    (`1 CNY = 11.5 RUB`). Purchases need a second hop through the payment
    request's currency — see _calculate_purchases.
    """
    income: Decimal = (
        await session.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount / LedgerEntry.exchange_rate), Decimal("0"))).where(
                LedgerEntry.order_id == order_id,
                LedgerEntry.type == LedgerEntryType.income,
            )
        )
    ).scalar_one()

    purchases: Decimal = await _calculate_purchases(order_id, session)

    logistics: Decimal = (
        await session.execute(
            select(
                func.coalesce(func.sum(Logistics.expense_amount / Logistics.exchange_rate), Decimal("0"))
            ).where(
                Logistics.order_id == order_id,
                Logistics.status == LogisticsStatus.accepted,
                Logistics.expense_amount.is_not(None),
            )
        )
    ).scalar_one()

    other_expenses: Decimal = (
        await session.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount / LedgerEntry.exchange_rate), Decimal("0"))).where(
                LedgerEntry.order_id == order_id,
                LedgerEntry.type == LedgerEntryType.expense,
            )
        )
    ).scalar_one()

    currency: str = (
        await session.execute(select(Order.currency).where(Order.id == order_id))
    ).scalar_one()

    is_ready = await _check_readiness(order_id, session)

    return ProfitBreakdown(
        income=income,
        purchases=purchases,
        logistics=logistics,
        other_expenses=other_expenses,
        profit=income - purchases - logistics - other_expenses,
        currency=currency,
        is_ready=is_ready,
    )
