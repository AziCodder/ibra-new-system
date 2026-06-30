from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment_request import PaymentRequestItem


async def count_product_dependencies(session: AsyncSession, product_id: int) -> int:
    """Count records that block deletion of a product.

    Extend this as new product-linked entities are added (logistics)
    — each phase that introduces such a model must add its count here.
    """
    return (
        await session.execute(
            select(func.count()).select_from(PaymentRequestItem).where(PaymentRequestItem.product_id == product_id)
        )
    ).scalar_one()
