from sqlalchemy.ext.asyncio import AsyncSession


async def count_order_dependencies(session: AsyncSession, order_id: int) -> int:
    """Count records that block deletion of an order.

    Extend this as new order-linked entities are added (items, payment
    requests, logistics, income/expense entries) — each phase that
    introduces such a model must add its count here.
    """
    # no dependent entities exist yet
    return 0
