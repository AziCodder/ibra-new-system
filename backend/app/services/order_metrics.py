from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.services.profit import ProfitBreakdown, calculate_profit


async def snapshot_order_metrics(
    order_id: int,
    session: AsyncSession,
    breakdown: ProfitBreakdown | None = None,
) -> bool:
    """Compute and persist profit_pct and processing_days when the order is ready.

    If `breakdown` is provided it is reused; otherwise calculate_profit is called.
    Returns True if metrics were written, False if the order is not ready yet.
    """
    if breakdown is None:
        breakdown = await calculate_profit(order_id, session)
    if not breakdown.is_ready:
        return False

    order = (await session.execute(select(Order).where(Order.id == order_id))).scalar_one()

    # profit_pct = profit / income * 100; guard against zero-income orders
    if breakdown.income and breakdown.income != Decimal("0"):
        pct = (breakdown.profit / breakdown.income * Decimal("100")).quantize(Decimal("0.0001"))
    else:
        pct = Decimal("0")

    order.profit_pct = pct
    order.processing_days = (date.today() - order.created_at.date()).days
    order.total_income = breakdown.income.quantize(Decimal("0.01"))
    order.profit_amount = breakdown.profit.quantize(Decimal("0.01"))
    await session.flush()
    return True
