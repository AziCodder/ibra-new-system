"""Wording of the Telegram notifications — the client filters chats by the hashtag,
so both the tag and the layout below it are part of the contract."""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.models.payment_request import PaymentRequestPriority
from app.services.notification_templates import format_amount, payment_request_message

REQUISITES = "周斯丽6217007200052740738中国建设银行股份有限公司深圳上步支行"


def test_payment_request_message_matches_the_agreed_layout(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "public_base_url", "https://82.25.60.93")

    message = payment_request_message(
        request_id=97,
        priority=PaymentRequestPriority.normal,
        requisites=REQUISITES,
        details="",
        total_amount=Decimal("16000.00"),
        currency="CNY",
        order_id=420,
    )

    assert message == (
        "#требуетсяоплата\n"
        "\n"
        "Запрос на оплату #97\n"
        "Приоритет: Обычно\n"
        "\n"
        f"Реквизиты: {REQUISITES}\n"
        "\n"
        "Детали: \n"
        "Итого: 16 000 CNY\n"
        "\n"
        "Ссылка: https://82.25.60.93/orders/420"
    )


def test_hashtag_is_the_first_line():
    message = payment_request_message(
        request_id=1,
        priority=PaymentRequestPriority.urgent,
        requisites="—",
        details="срочно",
        total_amount=Decimal("1"),
        currency="USD",
        order_id=1,
    )
    assert message.splitlines()[0] == "#требуетсяоплата"
    assert "Приоритет: Срочно" in message


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("16000"), "16 000"),
        (Decimal("1234.50"), "1 234,5"),
        (Decimal("0.25"), "0,25"),
        (Decimal("1000000"), "1 000 000"),
    ],
)
def test_amounts_read_like_in_the_app(value, expected):
    assert format_amount(value) == expected


@pytest.mark.asyncio
async def test_attachments_follow_the_text(monkeypatch):
    from app.services import notifications, storage, telegram_bot

    monkeypatch.setattr(telegram_bot, "send_message_with_retries", AsyncMock(return_value=True))
    send_file = AsyncMock(return_value=True)
    monkeypatch.setattr(telegram_bot, "send_document_with_retries", send_file)
    monkeypatch.setattr(storage.storage, "get", AsyncMock(return_value=b"invoice-bytes"))
    monkeypatch.setattr(notifications, "_record_delivery", AsyncMock())

    await notifications._deliver_and_log("-100123", "текст", ["a.pdf", "b.pdf"])

    assert [call.args[1] for call in send_file.await_args_list] == ["a.pdf", "b.pdf"]


@pytest.mark.asyncio
async def test_attachments_are_skipped_when_the_text_never_arrived(monkeypatch):
    """A file on its own tells the reader nothing, so it waits for the message."""
    from app.services import notifications, telegram_bot

    monkeypatch.setattr(telegram_bot, "send_message_with_retries", AsyncMock(return_value=False))
    send_file = AsyncMock(return_value=True)
    monkeypatch.setattr(telegram_bot, "send_document_with_retries", send_file)
    monkeypatch.setattr(notifications, "_record_delivery", AsyncMock())

    await notifications._deliver_and_log("-100123", "текст", ["a.pdf"])

    send_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_unreadable_file_does_not_break_the_send(monkeypatch):
    from app.services import notifications, storage, telegram_bot

    monkeypatch.setattr(telegram_bot, "send_message_with_retries", AsyncMock(return_value=True))
    send_file = AsyncMock(return_value=True)
    monkeypatch.setattr(telegram_bot, "send_document_with_retries", send_file)
    monkeypatch.setattr(
        storage.storage, "get", AsyncMock(side_effect=storage.StorageError("File not found"))
    )
    records = AsyncMock()
    monkeypatch.setattr(notifications, "_record_delivery", records)

    await notifications._deliver_and_log("-100123", "текст", ["gone.pdf"])

    send_file.assert_not_awaited()
    # Text row + one row explaining why the attachment never went out.
    assert records.await_count == 2
    assert "file not readable" in records.await_args_list[-1].args[3]


@pytest.mark.asyncio
async def test_notify_passes_attachments_through(monkeypatch):
    from app.services import notifications, telegram_bot

    notifications._background_tasks.clear()
    monkeypatch.setattr(telegram_bot, "get_bot", lambda: object())
    delivered = AsyncMock()
    monkeypatch.setattr(notifications, "_deliver_and_log", delivered)

    notifications.notify("-100123", "текст", ["a.pdf"])
    await asyncio.gather(*list(notifications._background_tasks))

    delivered.assert_awaited_once_with("-100123", "текст", ["a.pdf"])
