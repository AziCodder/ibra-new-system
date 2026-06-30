from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.logistics import Logistics
from app.models.payment_request import PaymentRequestItem


async def count_product_dependencies(session: AsyncSession, product_id: int) -> int:
    """Count records that block deletion of a product."""
    payment_request_items_count = (
        await session.execute(
            select(func.count()).select_from(PaymentRequestItem).where(PaymentRequestItem.product_id == product_id)
        )
    ).scalar_one()
    logistics_count = (
        await session.execute(select(func.count()).select_from(Logistics).where(Logistics.product_id == product_id))
    ).scalar_one()
    return payment_request_items_count + logistics_count
