from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment


async def count_payment_request_dependencies(session: AsyncSession, payment_request_id: int) -> int:
    """Count records that block deletion of a payment request.

    A request with at least one payment must not be deletable.
    """
    return (
        await session.execute(
            select(func.count()).select_from(Payment).where(Payment.payment_request_id == payment_request_id)
        )
    ).scalar_one()
