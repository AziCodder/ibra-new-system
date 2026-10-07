from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger_entry import LedgerEntry, LedgerEntryType
from app.models.logistics import Logistics, LogisticsItem, LogisticsStatus
from app.models.order import Order
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest
from app.models.product import Product
from app.services.product_payment_summary import get_unpaid_products


@dataclass(frozen=True)
class ReadinessBlocker:
    """One reason the order's profit isn't final yet."""

    kind: Literal["no_products", "in_transit", "not_received", "not_paid"]
    product_name: str | None = None
    # in_transit: shipments still on the way; not_received: quantity not yet
    # accepted; not_paid: cost not yet covered, in `currency`.
    amount: Decimal | None = None
    currency: str | None = None


@dataclass
class ProfitBreakdown:
    income: Decimal
    purchases: Decimal
    logistics: Decimal
    other_expenses: Decimal
    profit: Decimal
    currency: str
    blockers: list[ReadinessBlocker]

    @property
    def is_ready(self) -> bool:
        return not self.blockers


async def get_readiness_blockers(order_id: int, session: AsyncSession) -> list[ReadinessBlocker]:
    """Everything that keeps the order's profit from being final; empty means ready.

    Conditions (ТЗ §11, расширено правками 2026-10-01 п.1):
    1. The order has at least one product.
    2. No logistics entries are in_transit status (everything has been settled).
    3. For every product the sum of accepted logistics quantities >= product quantity.
    4. For every product the amount paid against it covers its full cost.
    """
    products = (
        await session.execute(
            select(Product.id, Product.name, Product.quantity)
            .where(Product.order_id == order_id)
            .order_by(Product.id)
        )
    ).all()
    if not products:
        return [ReadinessBlocker("no_products")]

    blockers: list[ReadinessBlocker] = []
    in_transit = (
        await session.execute(
            select(func.count())
            .select_from(Logistics)
            .where(Logistics.order_id == order_id, Logistics.status == LogisticsStatus.in_transit)
        )
    ).scalar_one()
    if in_transit:
        blockers.append(ReadinessBlocker("in_transit", amount=Decimal(in_transit)))

    accepted = dict(
        (
            await session.execute(
                select(LogisticsItem.product_id, func.sum(LogisticsItem.quantity))
                .join(Logistics, LogisticsItem.logistics_id == Logistics.id)
                .where(
                    LogisticsItem.product_id.in_([p.id for p in products]),
                    Logistics.status == LogisticsStatus.accepted,
                )
                .group_by(LogisticsItem.product_id)
            )
        ).all()
    )
    for product in products:
        received = accepted.get(product.id, Decimal("0"))
        if received < product.quantity:
            blockers.append(
                ReadinessBlocker("not_received", product_name=product.name, amount=product.quantity - received)
            )

    for unpaid in await get_unpaid_products(session, [order_id]):
        blockers.append(
            ReadinessBlocker("not_paid", product_name=unpaid.name, amount=unpaid.missing, currency=unpaid.currency)
        )
    return blockers


async def _check_readiness(order_id: int, session: AsyncSession) -> bool:
    return not await get_readiness_blockers(order_id, session)


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

    return ProfitBreakdown(
        income=income,
        purchases=purchases,
        logistics=logistics,
        other_expenses=other_expenses,
        profit=income - purchases - logistics - other_expenses,
        currency=currency,
        blockers=await get_readiness_blockers(order_id, session),
    )
