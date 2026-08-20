import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.client import Client
from app.models.order import Order, OrderStatus
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest, PaymentRequestItem
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.routers.logistics import create_logistics
from app.routers.payment_requests import create_payment_request
from app.routers.payments import create_payment
from app.schemas.logistics import LogisticsCreate, LogisticsItemIn
from app.schemas.payment import PaymentCreate
from app.schemas.payment_request import PaymentRequestCreate, PaymentRequestItemIn


async def _setup(code: str, quantity: Decimal = Decimal("10"), price: Decimal = Decimal("5.00")):
    async with async_session_factory() as session:
        client = Client(code=code, full_name=f"Race Test Client {code}")
        supplier = Supplier(name=f"Race Test Supplier {code}")
        owner = User(login=f"race_owner_{code}", password_hash=hash_password("x"), role=UserRole.manager, full_name="Owner")
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
            quantity=quantity,
            price=price,
            currency="USD",
        )
        session.add(product)
        await session.commit()
        await session.refresh(product)

        return client, supplier, owner, order, product


async def _cleanup(client_id: int, supplier_id: int, user_ids: list[int]):
    async with async_session_factory() as session:
        order_ids = select(Order.id).where(Order.client_id == client_id)
        request_ids = select(PaymentRequest.id).where(PaymentRequest.order_id.in_(order_ids))
        await session.execute(delete(Payment).where(Payment.payment_request_id.in_(request_ids)))
        await session.execute(delete(PaymentRequestItem).where(PaymentRequestItem.payment_request_id.in_(request_ids)))
        await session.execute(delete(PaymentRequest).where(PaymentRequest.order_id.in_(order_ids)))
        from app.models.logistics import Logistics

        await session.execute(delete(Logistics).where(Logistics.order_id.in_(order_ids)))
        await session.execute(delete(Product).where(Product.order_id.in_(order_ids)))
        await session.execute(delete(Order).where(Order.client_id == client_id))
        await session.execute(delete(Client).where(Client.id == client_id))
        await session.execute(delete(Supplier).where(Supplier.id == supplier_id))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_concurrent_logistics_creation_does_not_overship():
    client, supplier, owner, order, product = await _setup("RACELOG", quantity=Decimal("10"))
    try:
        results: list[tuple[str, object]] = []

        async def attempt():
            async with async_session_factory() as session:
                try:
                    out = await create_logistics(
                        order.id,
                        LogisticsCreate(
                    items=[LogisticsItemIn(product_id=product.id, quantity=Decimal("6"))],
                    ship_date=datetime.now(UTC)),
                        owner,
                        session,
                    )
                    results.append(("ok", out))
                except HTTPException as e:
                    results.append(("error", e.status_code))

        await asyncio.gather(attempt(), attempt())

        successes = [r for r in results if r[0] == "ok"]
        errors = [r for r in results if r[0] == "error"]
        assert len(successes) == 1, f"expected exactly one shipment to succeed, got {results}"
        assert len(errors) == 1
        assert errors[0][1] == 422
    finally:
        await _cleanup(client.id, supplier.id, [owner.id])


@pytest.mark.asyncio
async def test_concurrent_payment_request_creation_does_not_overcommit_product():
    # total value = 10 * 5.00 = 50.00; two concurrent requests of 30.00 each would jointly
    # overcommit to 60.00 if the product row weren't locked.
    client, supplier, owner, order, product = await _setup("RACEPRQ", quantity=Decimal("10"), price=Decimal("5.00"))
    try:
        results: list[tuple[str, object]] = []

        async def attempt():
            async with async_session_factory() as session:
                try:
                    out = await create_payment_request(
                        order.id,
                        PaymentRequestCreate(items=[PaymentRequestItemIn(product_id=product.id, amount=Decimal("30.00"))]),
                        owner,
                        session,
                    )
                    results.append(("ok", out))
                except HTTPException as e:
                    results.append(("error", e.status_code))

        await asyncio.gather(attempt(), attempt())

        successes = [r for r in results if r[0] == "ok"]
        errors = [r for r in results if r[0] == "error"]
        assert len(successes) == 1, f"expected exactly one payment request to succeed, got {results}"
        assert len(errors) == 1
        assert errors[0][1] == 422
    finally:
        await _cleanup(client.id, supplier.id, [owner.id])


@pytest.mark.asyncio
async def test_concurrent_payments_do_not_overpay_request():
    client, supplier, owner, order, product = await _setup("RACEPAY", quantity=Decimal("10"), price=Decimal("5.00"))
    try:
        async with async_session_factory() as session:
            request = PaymentRequest(order_id=order.id, created_by_id=owner.id)
            session.add(request)
            await session.commit()
            await session.refresh(request)
            session.add(PaymentRequestItem(payment_request_id=request.id, product_id=product.id, amount=Decimal("50.00")))
            await session.commit()

        results: list[tuple[str, object]] = []

        async def attempt():
            async with async_session_factory() as session:
                try:
                    out = await create_payment(
                        order.id,
                        request.id,
                        PaymentCreate(amount=Decimal("30.00"), exchange_rate=Decimal("1")),
                        owner,
                        session,
                    )
                    results.append(("ok", out))
                except HTTPException as e:
                    results.append(("error", e.status_code))

        await asyncio.gather(attempt(), attempt())

        successes = [r for r in results if r[0] == "ok"]
        errors = [r for r in results if r[0] == "error"]
        assert len(successes) == 1, f"expected exactly one payment to succeed, got {results}"
        assert len(errors) == 1
        assert errors[0][1] == 422
    finally:
        await _cleanup(client.id, supplier.id, [owner.id])
