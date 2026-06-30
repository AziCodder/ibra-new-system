from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment_request import PaymentRequest
from app.services.payment_remaining import get_payment_request_remaining
from app.services.profit import _check_readiness


async def check_can_complete(order_id: int, session: AsyncSession) -> bool:
    """Returns True when the order meets all criteria for completion (ТЗ §13).

    Conditions:
    1. Logistics settled: no in_transit, every product fully accepted.
    2. All payment requests fully paid (remaining_amount = 0).
    """
    if not await _check_readiness(order_id, session):
        return False

    pr_ids = (
        await session.execute(
            select(PaymentRequest.id).where(PaymentRequest.order_id == order_id)
        )
    ).scalars().all()

    for pr_id in pr_ids:
        remaining = await get_payment_request_remaining(session, pr_id)
        if remaining > Decimal("0"):
            return False

    return True
