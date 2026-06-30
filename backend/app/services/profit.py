from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger_entry import LedgerEntry, LedgerEntryType
from app.models.logistics import Logistics, LogisticsStatus
from app.models.order import Order
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest


@dataclass
class ProfitBreakdown:
    income: Decimal
    purchases: Decimal
    logistics: Decimal
    other_expenses: Decimal
    profit: Decimal
    currency: str


async def calculate_profit(order_id: int, session: AsyncSession) -> ProfitBreakdown:
    """Calculate profit for an order in its currency.

    Formula: Income − Purchases − Logistics − Other expenses = Profit

    Each component converts to order currency via: amount * exchange_rate,
    where exchange_rate is stored as "order-currency units per 1 operation-currency unit".
    """
    income: Decimal = (
        await session.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount * LedgerEntry.exchange_rate), Decimal("0"))).where(
                LedgerEntry.order_id == order_id,
                LedgerEntry.type == LedgerEntryType.income,
            )
        )
    ).scalar_one()

    purchases: Decimal = (
        await session.execute(
            select(func.coalesce(func.sum(Payment.amount * Payment.exchange_rate), Decimal("0")))
            .join(PaymentRequest, Payment.payment_request_id == PaymentRequest.id)
            .where(PaymentRequest.order_id == order_id)
        )
    ).scalar_one()

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
    )
