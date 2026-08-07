from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.logistics import Logistics, LogisticsItem, LogisticsStatus


@dataclass
class ProductShipment:
    id: int
    tracking: str | None
    quantity: Decimal
    status: LogisticsStatus


@dataclass
class ProductLogisticsTotals:
    shipped_quantity: Decimal = Decimal("0")
    accepted_quantity: Decimal = Decimal("0")
    shipments: list[ProductShipment] = field(default_factory=list)


async def get_products_logistics_totals(
    session: AsyncSession, product_ids: list[int]
) -> dict[int, ProductLogisticsTotals]:
    """Shipped/accepted quantities and the shipment list per product.

    "Shipped" counts every non-cancelled shipment, matching
    logistics_validation.get_product_already_shipped — so `quantity - shipped`
    is exactly the remaining balance the create-shipment form offers.
    "Accepted" counts only shipments already received. Cancelled shipments still
    appear in `shipments` (labelled by status) but add to neither total.
    A product with no shipments at all is omitted from the result
    (mirrors product_payment_summary.get_products_payment_totals's convention).
    """
    if not product_ids:
        return {}

    rows = (
        await session.execute(
            select(
                LogisticsItem.product_id,
                Logistics.id,
                Logistics.tracking,
                LogisticsItem.quantity,
                Logistics.status,
            )
            .join(Logistics, LogisticsItem.logistics_id == Logistics.id)
            .where(LogisticsItem.product_id.in_(product_ids))
            .order_by(Logistics.ship_date, Logistics.id)
        )
    ).all()

    totals: dict[int, ProductLogisticsTotals] = {}
    for product_id, logistics_id, tracking, quantity, status in rows:
        entry = totals.setdefault(product_id, ProductLogisticsTotals())
        entry.shipments.append(
            ProductShipment(id=logistics_id, tracking=tracking, quantity=quantity, status=status)
        )
        if status != LogisticsStatus.cancelled:
            entry.shipped_quantity += quantity
        if status == LogisticsStatus.accepted:
            entry.accepted_quantity += quantity

    return totals
