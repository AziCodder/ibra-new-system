from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment_request import PaymentRequestItem
from app.models.product import Product


class PaymentRequestValidationError(Exception):
    """Raised when a payment request's items violate a business rule.

    Routers catch this and translate it to HTTP 422 — kept as a plain
    exception here (not HTTPException) so the validation logic stays
    reusable outside the request/response cycle, mirroring StorageError.
    """


async def get_product_remaining(
    session: AsyncSession, product_id: int, exclude_request_id: int | None = None
) -> Decimal:
    """Portion of a product's total cost not yet covered by any payment request item.

    `exclude_request_id` lets an in-progress edit of an existing request
    re-validate without double-counting its own already-saved items.
    """
    product = (await session.execute(select(Product).where(Product.id == product_id))).scalar_one()
    total = product.quantity * product.price

    requested_query = select(func.coalesce(func.sum(PaymentRequestItem.amount), 0)).where(
        PaymentRequestItem.product_id == product_id
    )
    if exclude_request_id is not None:
        requested_query = requested_query.where(PaymentRequestItem.payment_request_id != exclude_request_id)
    already_requested = (await session.execute(requested_query)).scalar_one()

    return total - already_requested


async def validate_payment_request_items(
    session: AsyncSession,
    items: list[tuple[int, Decimal]],
    exclude_request_id: int | None = None,
) -> None:
    """Validate (product_id, amount) pairs intended for one payment request.

    Raises PaymentRequestValidationError if the items span more than one
    product currency, or if any item's amount exceeds that product's
    remaining (not-yet-requested) balance.
    """
    if not items:
        raise PaymentRequestValidationError("Payment request must include at least one item")

    product_ids = [product_id for product_id, _ in items]
    products = (await session.execute(select(Product).where(Product.id.in_(product_ids)))).scalars().all()
    products_by_id = {p.id: p for p in products}

    for product_id, _ in items:
        if product_id not in products_by_id:
            raise PaymentRequestValidationError(f"Product {product_id} not found")

    currencies = {products_by_id[product_id].currency for product_id, _ in items}
    if len(currencies) > 1:
        raise PaymentRequestValidationError(
            f"All items in a payment request must use the same currency, got: {', '.join(sorted(currencies))}"
        )

    for product_id, amount in items:
        remaining = await get_product_remaining(session, product_id, exclude_request_id=exclude_request_id)
        if amount > remaining:
            raise PaymentRequestValidationError(
                f"Amount {amount} for product {product_id} exceeds remaining balance {remaining}"
            )
