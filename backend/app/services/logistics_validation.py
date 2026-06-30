from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.logistics import Logistics, LogisticsStatus
from app.models.product import Product


class LogisticsValidationError(Exception):
    """Raised when a logistics record's quantity violates a business rule.

    Routers catch this and translate it to HTTP 422 — kept as a plain
    exception here (not HTTPException), mirroring PaymentRequestValidationError.
    """


async def get_product_shipped_remaining(
    session: AsyncSession, product_id: int, exclude_logistics_id: int | None = None
) -> Decimal:
    """Portion of a product's purchased quantity not yet committed to a shipment.

    Cancelled shipments (`status=cancelled`) are excluded from the already-shipped
    sum — a cancelled shipment never left or was voided, so its quantity is free
    to be re-shipped. `exclude_logistics_id` lets an in-progress edit of an
    existing shipment re-validate without double-counting its own saved quantity.
    """
    product = (await session.execute(select(Product).where(Product.id == product_id))).scalar_one()

    shipped_query = select(func.coalesce(func.sum(Logistics.quantity), 0)).where(
        Logistics.product_id == product_id,
        Logistics.status != LogisticsStatus.cancelled,
    )
    if exclude_logistics_id is not None:
        shipped_query = shipped_query.where(Logistics.id != exclude_logistics_id)
    already_shipped = (await session.execute(shipped_query)).scalar_one()

    return product.quantity - already_shipped


async def validate_logistics_quantity(
    session: AsyncSession,
    product_id: int,
    quantity: Decimal,
    exclude_logistics_id: int | None = None,
) -> None:
    """Raise LogisticsValidationError if quantity exceeds the product's shipped remaining."""
    remaining = await get_product_shipped_remaining(session, product_id, exclude_logistics_id=exclude_logistics_id)
    if quantity > remaining:
        raise LogisticsValidationError(
            f"Quantity {quantity} for product {product_id} exceeds shipped remaining balance {remaining}"
        )
