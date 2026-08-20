from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger_entry import LedgerEntry, LedgerEntryType
from app.models.logistics import Logistics, LogisticsItem, LogisticsStatus
from app.models.order import Order
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest
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

    One conversion, no hops: a payment is made in its request's currency, and its
    own `exchange_rate` is the rate that money was bought at, quoted towards the
    order's currency (`1 CNY = 11.5 RUB` -> 11.5). So each payment costs
    `amount * exchange_rate` in the order's totals and they simply add up.

    The rate rides on the payment rather than on the product deliberately: the
    same request is often settled in instalments bought on different days — 50 000
    CNY at 12, then 25 200 at 12.1 — and only a per-payment rate can record what
    each one actually cost. `Product.exchange_rate` prices the goods and takes no
    part here; using it too would convert the same money twice.
    """
    return (
        await session.execute(
            select(func.coalesce(func.sum(Payment.amount * Payment.exchange_rate), Decimal("0")))
            .join(PaymentRequest, Payment.payment_request_id == PaymentRequest.id)
            .where(PaymentRequest.order_id == order_id)
        )
    ).scalar_one()


async def calculate_profit(order_id: int, session: AsyncSession) -> ProfitBreakdown:
    """Calculate profit for an order in its currency.

    Formula: Income − Purchases − Logistics − Other expenses = Profit

    Every term converts to the order currency the same way — `amount *
    exchange_rate`, where the rate is stored as "order-currency units per 1
    operation-currency unit", the direction the forms ask for (`1 CNY = 11.5
    RUB`). That holds for payments too; see _calculate_purchases.
    """
    income: Decimal = (
        await session.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount * LedgerEntry.exchange_rate), Decimal("0"))).where(
                LedgerEntry.order_id == order_id,
                LedgerEntry.type == LedgerEntryType.income,
            )
        )
    ).scalar_one()

    purchases: Decimal = await _calculate_purchases(order_id, session)

    logistics: Decimal = (
        await session.execute(
            select(
                func.coalesce(func.sum(Logistics.expense_amount * Logistics.exchange_rate), Decimal("0"))
            ).where(
                Logistics.order_id == order_id,
                Logistics.status == LogisticsStatus.accepted,
                Logistics.expense_amount.is_not(None),
            )
        )
    ).scalar_one()

    other_expenses: Decimal = (
        await session.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount * LedgerEntry.exchange_rate), Decimal("0"))).where(
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
