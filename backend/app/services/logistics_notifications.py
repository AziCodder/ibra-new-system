from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.logistics import Logistics, LogisticsStatus
from app.models.order import Order
from app.services.notification_templates import shipment_sent_message
from app.services.notifications import notify_targets
from app.services.telegram_groups import get_client_send_targets


async def notify_shipment_sent(logistics: Logistics, session: AsyncSession) -> None:
    """Announce a departed shipment in every chat the client is served by.

    Only for shipments that are actually on their way: an admin can enter one
    already marked accepted, and that is a record of something that arrived
    long ago, not a departure worth announcing.
    """
    if logistics.status != LogisticsStatus.in_transit:
        return

    order = (await session.execute(select(Order).where(Order.id == logistics.order_id))).scalar_one()
    client = (await session.execute(select(Client).where(Client.id == order.client_id))).scalar_one()

    message = shipment_sent_message(
        ship_date=logistics.ship_date,
        tracking=logistics.tracking,
        details=logistics.details,
        order_id=order.id,
    )

    targets = await get_client_send_targets(client, session)
    # The waybill travels with the notice — it is what the recipient checks the
    # parcel against.
    notify_targets(
        targets,
        client.telegram_chat_id,
        message,
        [logistics.invoice_file_key] if logistics.invoice_file_key else [],
    )
