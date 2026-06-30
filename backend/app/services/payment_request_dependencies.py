from sqlalchemy.ext.asyncio import AsyncSession


async def count_payment_request_dependencies(session: AsyncSession, payment_request_id: int) -> int:
    """Count records that block deletion of a payment request.

    Extend this once the Payment model lands (Phase 6.4) — a request
    with at least one payment must not be deletable.
    """
    # no dependent entities exist yet
    return 0
