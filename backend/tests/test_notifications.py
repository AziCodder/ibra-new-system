import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.client import Client
from app.models.order import Order, OrderStatus
from app.models.payment_request import PaymentRequest, PaymentRequestItem
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.telegram_group import ClientTelegramGroup, TelegramGroup
from app.models.user import User, UserRole
from app.routers.payment_requests import create_payment_request
from app.schemas.payment_request import PaymentRequestCreate, PaymentRequestItemIn
from app.services.notifications import notify


def test_notify_logs_message(caplog):
    with caplog.at_level("INFO", logger="notifications"):
        notify("https://t.me/some-group", "test message")
    assert "https://t.me/some-group" in caplog.text
    assert "test message" in caplog.text


@pytest.mark.asyncio
async def test_notify_schedules_background_delivery_when_bot_configured(monkeypatch):
    from app.services import notifications, telegram_bot

    notifications._background_tasks.clear()
    monkeypatch.setattr(telegram_bot, "get_bot", lambda: object())  # bot configured
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(telegram_bot, "send_message_with_retries", sender)
    # Stub out persistence so this scheduling test stays isolated from the DB.
    recorder = AsyncMock()
    monkeypatch.setattr(notifications, "_record_delivery", recorder)

    notifications.notify("-100123", "hello")  # returns immediately, non-blocking
    # Drain the task scheduled onto the running loop.
    await asyncio.gather(*list(notifications._background_tasks))

    sender.assert_awaited_once_with("-100123", "hello")
    recorder.assert_awaited_once()  # delivery outcome persisted (Итог 11.5)


@pytest.mark.asyncio
async def test_notify_without_bot_does_not_schedule(monkeypatch):
    from app.services import notifications, telegram_bot

    notifications._background_tasks.clear()
    monkeypatch.setattr(telegram_bot, "get_bot", lambda: None)  # no bot configured
    sender = AsyncMock()
    monkeypatch.setattr(telegram_bot, "send_message_with_retries", sender)

    notifications.notify("-100123", "hello")

    sender.assert_not_awaited()
    assert not notifications._background_tasks


async def _setup():
    async with async_session_factory() as session:
        client = Client(
            code="TSTNOTIFY",
            full_name="Notify Test Client",
            telegram_group_link="https://t.me/notify-test-group",
            telegram_chat_id="-1001234567890",
        )
        supplier = Supplier(name="Notify Test Supplier")
        owner = User(login="notify_owner", password_hash=hash_password("x"), role=UserRole.manager, full_name="Owner")
        session.add_all([client, supplier, owner])
        await session.commit()
        for obj in (client, supplier, owner):
            await session.refresh(obj)

        order = Order(
            number=f"{client.code}-1",
            client_id=client.id,
            manager_id=owner.id,
            status=OrderStatus.in_progress,
            currency="USD",
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)

        product = Product(
            order_id=order.id,
            supplier_id=supplier.id,
            name="Widget",
            quantity=Decimal("10"),
            price=Decimal("5.00"),
            currency="USD",
        )
        session.add(product)
        await session.commit()
        await session.refresh(product)

        return client, supplier, owner, order, product


async def _cleanup(client_id: int, supplier_id: int, user_ids: list[int]):
    async with async_session_factory() as session:
        order_ids = select(Order.id).where(Order.client_id == client_id)
        await session.execute(
            delete(PaymentRequestItem).where(
                PaymentRequestItem.payment_request_id.in_(
                    select(PaymentRequest.id).where(PaymentRequest.order_id.in_(order_ids))
                )
            )
        )
        await session.execute(delete(PaymentRequest).where(PaymentRequest.order_id.in_(order_ids)))
        await session.execute(delete(Product).where(Product.order_id.in_(order_ids)))
        await session.execute(delete(Order).where(Order.client_id == client_id))
        await session.execute(delete(Client).where(Client.id == client_id))
        await session.execute(delete(Supplier).where(Supplier.id == supplier_id))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_create_payment_request_calls_notify_with_client_chat_and_order_details():
    client, supplier, owner, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            with patch("app.routers.payment_requests.notify_targets") as mock_notify:
                await create_payment_request(
                    order.id,
                    PaymentRequestCreate(
                        requisites="bank details",
                        details="urgent purchase",
                        items=[PaymentRequestItemIn(product_id=product.id, amount=Decimal("20.00"))],
                    ),
                    owner,
                    session,
                )

            mock_notify.assert_called_once()
            targets, fallback, message, file_keys = mock_notify.call_args[0]
            # No chat is attached to this client, so it falls back to their private
            # chat id — not the human-facing t.me link.
            assert targets == []
            assert fallback == "-1001234567890"
            assert message.splitlines()[0] == "#требуетсяоплата"
            assert "Итого: 20 USD" in message
            assert "Реквизиты: bank details" in message
            assert "Детали: urgent purchase" in message
            assert f"/orders/{order.id}" in message  # order link present
            assert file_keys == []  # nothing was attached to this request
    finally:
        await _cleanup(client.id, supplier.id, [owner.id])


@pytest.mark.asyncio
async def test_create_payment_request_requires_group_ids_when_client_has_multiple_groups():
    client, supplier, owner, order, product = await _setup()
    group_a_id = group_b_id = None
    try:
        async with async_session_factory() as session:
            group_a = TelegramGroup(chat_id="-100903001", title="Group A")
            group_b = TelegramGroup(chat_id="-100903002", title="Group B")
            session.add_all([group_a, group_b])
            await session.commit()
            await session.refresh(group_a)
            await session.refresh(group_b)
            group_a_id, group_b_id = group_a.id, group_b.id
            session.add(ClientTelegramGroup(client_id=client.id, group_id=group_a_id))
            session.add(ClientTelegramGroup(client_id=client.id, group_id=group_b_id))
            await session.commit()

        async with async_session_factory() as session:
            with patch("app.routers.payment_requests.notify_targets") as mock_notify:
                with pytest.raises(HTTPException) as exc_info:
                    await create_payment_request(
                        order.id,
                        PaymentRequestCreate(
                            requisites="bank details",
                            items=[PaymentRequestItemIn(product_id=product.id, amount=Decimal("20.00"))],
                        ),
                        owner,
                        session,
                    )
            assert exc_info.value.status_code == 422
            mock_notify.assert_not_called()

        async with async_session_factory() as session:
            remaining = (
                await session.execute(select(PaymentRequest).where(PaymentRequest.order_id == order.id))
            ).scalars().all()
            assert remaining == []  # nothing persisted — validated before the row was created
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(ClientTelegramGroup).where(ClientTelegramGroup.client_id == client.id))
            if group_a_id is not None:
                await session.execute(delete(TelegramGroup).where(TelegramGroup.id.in_([group_a_id, group_b_id])))
            await session.commit()
        await _cleanup(client.id, supplier.id, [owner.id])


@pytest.mark.asyncio
async def test_create_payment_request_sends_to_all_chosen_groups():
    client, supplier, owner, order, product = await _setup()
    group_a_id = group_b_id = None
    try:
        async with async_session_factory() as session:
            group_a = TelegramGroup(chat_id="-100904001", title="Group A")
            group_b = TelegramGroup(chat_id="-100904002", title="Group B")
            session.add_all([group_a, group_b])
            await session.commit()
            await session.refresh(group_a)
            await session.refresh(group_b)
            group_a_id, group_b_id = group_a.id, group_b.id
            session.add(ClientTelegramGroup(client_id=client.id, group_id=group_a_id))
            session.add(ClientTelegramGroup(client_id=client.id, group_id=group_b_id))
            await session.commit()

        async with async_session_factory() as session:
            with patch("app.routers.payment_requests.notify_targets") as mock_notify:
                await create_payment_request(
                    order.id,
                    PaymentRequestCreate(
                        requisites="bank details",
                        items=[PaymentRequestItemIn(product_id=product.id, amount=Decimal("20.00"))],
                        group_ids=[group_a_id, group_b_id],
                    ),
                    owner,
                    session,
                )
            mock_notify.assert_called_once()
            targets = {t["chat_id"] for t in mock_notify.call_args[0][0]}
            assert targets == {"-100904001", "-100904002"}
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(ClientTelegramGroup).where(ClientTelegramGroup.client_id == client.id))
            if group_a_id is not None:
                await session.execute(delete(TelegramGroup).where(TelegramGroup.id.in_([group_a_id, group_b_id])))
            await session.commit()
        await _cleanup(client.id, supplier.id, [owner.id])
