import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.order import Order
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest, PaymentRequestItem
from app.models.product import Product
from app.services.notification_templates import payment_made_message
from app.services.notifications import notify_targets
from app.services.payment_remaining import get_payment_request_paid, get_payment_request_total
from app.services.telegram_groups import get_client_send_targets

logger = logging.getLogger("notifications")


async def _request_currency(request_id: int, session: AsyncSession) -> str:
    """The currency a request is denominated in — that of the products on it.

    Mirrors how the payment-request summaries derive it (payment_requests_global).
    A request always has at least one item when created through the API.
    """
    currency = (
        await session.execute(
            select(Product.currency)
            .join(PaymentRequestItem, PaymentRequestItem.product_id == Product.id)
            .where(PaymentRequestItem.payment_request_id == request_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    return currency or ""


async def notify_payment_recorded(payment: Payment, session: AsyncSession) -> None:
    """Announce a recorded payment in every chat the client is served by.

    Call after the payment is committed: the remainder quoted in the message is
    read back from the database, so it already accounts for this payment.

    Nothing in here may fail the request. The payment is already saved by this
    point, so raising would show the operator an error for money that did go in —
    and invite them to enter it twice.
    """
    try:
        request = (
            await session.execute(
                select(PaymentRequest).where(PaymentRequest.id == payment.payment_request_id)
            )
        ).scalar_one()
        order = (await session.execute(select(Order).where(Order.id == request.order_id))).scalar_one()
        client = (await session.execute(select(Client).where(Client.id == order.client_id))).scalar_one()

        # Deliberately not get_payment_request_remaining: that one locks the request
        # row until the transaction ends, which is right when a payment is being
        # validated and pointless for a message that only reports the number.
        total = await get_payment_request_total(session, request.id)
        paid = await get_payment_request_paid(session, request.id)

        message = payment_made_message(
            request_id=request.id,
            amount=payment.amount,
            currency=payment.currency,
            exchange_rate=payment.exchange_rate,
            remaining_after=total - paid,
            request_currency=await _request_currency(request.id, session),
            note=payment.note,
            order_id=order.id,
        )

        targets = await get_client_send_targets(client, session)
        # The receipt the payer attached is the proof of payment — it goes along.
        notify_targets(
            targets,
            client.telegram_chat_id,
            message,
            [payment.file_key] if payment.file_key else [],
        )
    except Exception:  # noqa: BLE001 - see the docstring
        logger.exception("Payment %s recorded, but its notification could not be built", payment.id)
