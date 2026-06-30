from sqlalchemy.ext.asyncio import AsyncSession


async def count_product_dependencies(session: AsyncSession, product_id: int) -> int:
    """Count records that block deletion of a product.

    Extend this as new product-linked entities are added (payment
    requests, logistics) — each phase that introduces such a model
    must add its count here.
    """
    # no dependent entities exist yet
    return 0
