"""Shared builders for tests that seed rows directly, bypassing the API."""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.logistics import Logistics, LogisticsItem


async def add_shipment(
    session: AsyncSession,
    *,
    order_id: int,
    created_by_id: int,
    lines: list[tuple[int, Decimal]],
    **fields,
) -> Logistics:
    """Insert a shipment and its product lines, the way the API does.

    `lines` is a list of (product_id, quantity). Flushes so the caller gets an id,
    but leaves committing to the caller.
    """
    logistics = Logistics(order_id=order_id, created_by_id=created_by_id, **fields)
    session.add(logistics)
    await session.flush()
    for product_id, quantity in lines:
        session.add(LogisticsItem(logistics_id=logistics.id, product_id=product_id, quantity=quantity))
    return logistics
