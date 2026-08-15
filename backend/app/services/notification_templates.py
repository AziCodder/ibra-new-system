"""Texts of the Telegram notifications, kept apart from the routers that send them.

Every template opens with its hashtag on the first line — that is what the client
filters their chats by, so the tag must stay the very first thing in the message.
"""

from decimal import Decimal

from app.core.config import settings
from app.models.payment_request import PaymentRequestPriority

PRIORITY_LABELS: dict[PaymentRequestPriority, str] = {
    PaymentRequestPriority.low: "Низкий",
    PaymentRequestPriority.normal: "Обычно",
    PaymentRequestPriority.urgent: "Срочно",
}


def format_amount(value: Decimal) -> str:
    """16000 -> "16 000", 1234.5 -> "1 234,5" — as the amounts read in the app."""
    quantized = Decimal(value).quantize(Decimal("0.01"))
    whole, _, fraction = f"{quantized:,.2f}".partition(".")
    whole = whole.replace(",", " ")
    fraction = fraction.rstrip("0")
    return f"{whole},{fraction}" if fraction else whole


def order_link(order_id: int) -> str:
    return f"{settings.public_base_url.rstrip('/')}/orders/{order_id}"


def payment_request_message(
    *,
    request_id: int,
    priority: PaymentRequestPriority,
    requisites: str,
    details: str,
    total_amount: Decimal,
    currency: str,
    order_id: int,
) -> str:
    """«Требуется оплата» — sent when a payment request is created."""
    return (
        "#требуетсяоплата\n"
        "\n"
        f"Запрос на оплату #{request_id}\n"
        f"Приоритет: {PRIORITY_LABELS.get(priority, priority)}\n"
        "\n"
        f"Реквизиты: {requisites}\n"
        "\n"
        f"Детали: {details}\n"
        f"Итого: {format_amount(total_amount)} {currency}\n"
        "\n"
        f"Ссылка: {order_link(order_id)}"
    )
