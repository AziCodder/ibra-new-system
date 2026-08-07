from collections import Counter
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.logistics import Logistics, LogisticsItem, LogisticsStatus
from app.models.product import Product


class LogisticsValidationError(Exception):
    """Raised when a logistics record's quantity violates a business rule.

    Routers catch this and translate it to HTTP 422 — kept as a plain
    exception here (not HTTPException), mirroring PaymentRequestValidationError.
    """


async def get_product_already_shipped(
    session: AsyncSession, product_id: int, exclude_logistics_id: int | None = None
) -> Decimal:
    """Sum of quantities already committed to a (non-cancelled) shipment for a product.

    Cancelled shipments (`status=cancelled`) are excluded — a cancelled shipment
    never left or was voided, so its quantity is free to be re-shipped.
    `exclude_logistics_id` lets an in-progress edit of an existing shipment
    re-validate without double-counting its own saved lines.
    """
    shipped_query = (
        select(func.coalesce(func.sum(LogisticsItem.quantity), 0))
        .join(Logistics, LogisticsItem.logistics_id == Logistics.id)
        .where(
            LogisticsItem.product_id == product_id,
            Logistics.status != LogisticsStatus.cancelled,
        )
    )
    if exclude_logistics_id is not None:
        shipped_query = shipped_query.where(Logistics.id != exclude_logistics_id)
    return (await session.execute(shipped_query)).scalar_one()


async def get_product_shipped_remaining(
    session: AsyncSession, product_id: int, exclude_logistics_id: int | None = None
) -> Decimal:
    """Portion of a product's purchased quantity not yet committed to a shipment."""
    # Locks the product row until the caller's transaction commits, so two concurrent
    # shipment creations against the same product can't both read the same "remaining"
    # value and jointly overcommit it (mirrors order_number.py's with_for_update pattern).
    product = (
        await session.execute(select(Product).where(Product.id == product_id).with_for_update())
    ).scalar_one()

    already_shipped = await get_product_already_shipped(session, product_id, exclude_logistics_id)
    return product.quantity - already_shipped


async def validate_logistics_items(
    session: AsyncSession,
    items: list[tuple[int, Decimal]],
    exclude_logistics_id: int | None = None,
) -> None:
    """Validate the (product_id, quantity) lines intended for one shipment.

    Each line is checked against its own product's shipped remaining — a shipment
    carrying several products never pools their balances. Products are locked in
    a stable order so two concurrent shipments over the same pair can't deadlock.
    """
    if not items:
        raise LogisticsValidationError("Shipment must include at least one product")

    duplicates = [product_id for product_id, count in Counter(pid for pid, _ in items).items() if count > 1]
    if duplicates:
        raise LogisticsValidationError(
            f"Product(s) {sorted(duplicates)} listed more than once in the same shipment"
        )

    for product_id, quantity in sorted(items):
        remaining = await get_product_shipped_remaining(
            session, product_id, exclude_logistics_id=exclude_logistics_id
        )
        if quantity > remaining:
            raise LogisticsValidationError(
                f"Quantity {quantity} for product {product_id} exceeds shipped remaining balance {remaining}"
            )
