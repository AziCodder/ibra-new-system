from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.logistics import Logistics
from app.models.payment_request import PaymentRequest
from app.models.product import Product


async def count_order_dependencies(session: AsyncSession, order_id: int) -> int:
    """Count records that block deletion of an order.

    Extend this as new order-linked entities are added (income/expense
    entries) — each phase that introduces such a model must add its count here.
    """
    products_count = (
        await session.execute(select(func.count()).select_from(Product).where(Product.order_id == order_id))
    ).scalar_one()
    payment_requests_count = (
        await session.execute(
            select(func.count()).select_from(PaymentRequest).where(PaymentRequest.order_id == order_id)
        )
    ).scalar_one()
    logistics_count = (
        await session.execute(select(func.count()).select_from(Logistics).where(Logistics.order_id == order_id))
    ).scalar_one()
    return products_count + payment_requests_count + logistics_count
