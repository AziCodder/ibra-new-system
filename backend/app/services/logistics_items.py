from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.logistics import LogisticsItem
from app.models.product import Product


@dataclass
class ShipmentLine:
    product_id: int
    product_name: str
    quantity: Decimal


async def get_logistics_items(
    session: AsyncSession, logistics_ids: list[int]
) -> dict[int, list[ShipmentLine]]:
    """Lines of several shipments at once, keyed by shipment id.

    Batched so list endpoints don't run one query per shipment. Shipments with no
    lines are omitted; callers default them to an empty list.
    """
    if not logistics_ids:
        return {}

    rows = (
        await session.execute(
            select(LogisticsItem.logistics_id, LogisticsItem.product_id, Product.name, LogisticsItem.quantity)
            .join(Product, LogisticsItem.product_id == Product.id)
            .where(LogisticsItem.logistics_id.in_(logistics_ids))
            .order_by(LogisticsItem.id)
        )
    ).all()

    items: dict[int, list[ShipmentLine]] = {}
    for logistics_id, product_id, product_name, quantity in rows:
        items.setdefault(logistics_id, []).append(
            ShipmentLine(product_id=product_id, product_name=product_name, quantity=quantity)
        )
    return items
