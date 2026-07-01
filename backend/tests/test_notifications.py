import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.client import Client
from app.models.order import Order, OrderStatus
from app.models.payment_request import PaymentRequest, PaymentRequestItem
from app.models.product import Product
from app.models.supplier import Supplier
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

    notifications.notify("-100123", "hello")  # returns immediately, non-blocking
    # Drain the task scheduled onto the running loop.
    await asyncio.gather(*list(notifications._background_tasks))

    sender.assert_awaited_once_with("-100123", "hello")


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
            code="TSTNOTIFY", full_name="Notify Test Client", telegram_group_link="https://t.me/notify-test-group"
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
async def test_create_payment_request_calls_notify_with_client_group_and_order_details():
    client, supplier, owner, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            with patch("app.routers.payment_requests.notify") as mock_notify:
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
            target, message = mock_notify.call_args[0]
            assert target == "https://t.me/notify-test-group"
            assert order.number in message
            assert "20.00" in message or "20" in message
            assert "bank details" in message
            assert "urgent purchase" in message
    finally:
        await _cleanup(client.id, supplier.id, [owner.id])
