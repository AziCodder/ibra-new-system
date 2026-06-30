from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.order import Order


async def generate_order_number(session: AsyncSession, client_id: int) -> str:
    """Generate the next sequential order number for a client, e.g. M33-1, M33-2.

    Locks the client row (SELECT ... FOR UPDATE) to serialize number
    generation per client and avoid collisions under concurrent inserts.
    """
    result = await session.execute(select(Client).where(Client.id == client_id).with_for_update())
    client = result.scalar_one()

    count_result = await session.execute(
        select(func.count()).select_from(Order).where(Order.client_id == client_id)
    )
    count = count_result.scalar_one()

    return f"{client.code}-{count + 1}"
