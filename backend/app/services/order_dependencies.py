from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger_entry import LedgerEntry
from app.models.logistics import Logistics
from app.models.payment_request import PaymentRequest


async def count_order_dependencies(session: AsyncSession, order_id: int) -> int:
    """Count records that block deletion of an order.

    Per ТЗ §6, products alone do NOT block deletion — an order's товары cascade-delete
    along with it (see products.order_id FK ondelete=CASCADE) as long as nothing
    downstream (a payment request or logistics record) references them.
    """
    payment_requests_count = (
        await session.execute(
            select(func.count()).select_from(PaymentRequest).where(PaymentRequest.order_id == order_id)
        )
    ).scalar_one()
    logistics_count = (
        await session.execute(select(func.count()).select_from(Logistics).where(Logistics.order_id == order_id))
    ).scalar_one()
    ledger_entries_count = (
        await session.execute(
            select(func.count()).select_from(LedgerEntry).where(LedgerEntry.order_id == order_id)
        )
    ).scalar_one()
    return payment_requests_count + logistics_count + ledger_entries_count


async def order_dependency_breakdown(session: AsyncSession, order_id: int) -> dict[str, int]:
    """Per-category counts of records that block deletion of an order (see count_order_dependencies)."""
    payment_requests_count = (
        await session.execute(
            select(func.count()).select_from(PaymentRequest).where(PaymentRequest.order_id == order_id)
        )
    ).scalar_one()
    logistics_count = (
        await session.execute(select(func.count()).select_from(Logistics).where(Logistics.order_id == order_id))
    ).scalar_one()
    ledger_entries_count = (
        await session.execute(
            select(func.count()).select_from(LedgerEntry).where(LedgerEntry.order_id == order_id)
        )
    ).scalar_one()
    return {
        "payment_requests": payment_requests_count,
        "logistics": logistics_count,
        "ledger_entries": ledger_entries_count,
    }
