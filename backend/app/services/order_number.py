from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.order import Order


async def generate_order_number(session: AsyncSession, client_id: int) -> str:
    """Generate the next sequential order number for a client, e.g. M33-1, M33-2.

    Counts up from the highest suffix already issued to this client rather than
    from how many orders it currently has: deleting an order must not make the
    next one reuse a number. (With a count, a client left holding only M1-2
    would be handed M1-2 again, and `orders.number` is unique — the insert would
    fail with a 500 and no order could ever be created for that client again.)
    A suffix is therefore never reused, even once its order is gone.

    Locks the client row (SELECT ... FOR UPDATE) to serialize number
    generation per client and avoid collisions under concurrent inserts.
    """
    result = await session.execute(select(Client).where(Client.id == client_id).with_for_update())
    client = result.scalar_one()

    issued = (
        await session.execute(select(Order.number).where(Order.client_id == client_id))
    ).scalars().all()

    # Numbers carrying another prefix belong to a previous client code — renaming
    # a client legitimately restarts its numbering at 1.
    prefix = f"{client.code}-"
    highest = 0
    for number in issued:
        suffix = number.removeprefix(prefix) if number.startswith(prefix) else ""
        if suffix.isdigit():
            highest = max(highest, int(suffix))

    return f"{client.code}-{highest + 1}"
