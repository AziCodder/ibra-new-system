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
from app.routers.orders import delete_order
from app.routers.payment_requests import delete_payment_request, get_payment_request
from app.routers.payments import create_payment, list_payments
from app.schemas.payment import PaymentCreate
from app.services.payment_request_dependencies import count_payment_request_dependencies


async def _setup():
    async with async_session_factory() as session:
        client = Client(code="TSTPAY", full_name="Payments Test Client")
        supplier = Supplier(name="Payments Test Supplier")
        owner = User(login="pay_owner", password_hash=hash_password("x"), role=UserRole.manager, full_name="Owner Manager")
        other = User(login="pay_other", password_hash=hash_password("x"), role=UserRole.manager, full_name="Other Manager")
        observer = User(login="pay_observer", password_hash=hash_password("x"), role=UserRole.observer, full_name="Observer")
        session.add_all([client, supplier, owner, other, observer])
        await session.commit()
        for obj in (client, supplier, owner, other, observer):
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

        request = PaymentRequest(order_id=order.id, created_by_id=owner.id)
        session.add(request)
        await session.commit()
        await session.refresh(request)

        session.add(PaymentRequestItem(payment_request_id=request.id, product_id=product.id, amount=Decimal("50.00")))
        await session.commit()

        return client, supplier, owner, other, observer, order, product, request


async def _cleanup(client_id: int, supplier_id: int, user_ids: list[int]):
    async with async_session_factory() as session:
        order_ids = select(Order.id).where(Order.client_id == client_id)
        request_ids = select(PaymentRequest.id).where(PaymentRequest.order_id.in_(order_ids))
        await session.execute(delete(Payment).where(Payment.payment_request_id.in_(request_ids)))
        await session.execute(delete(PaymentRequestItem).where(PaymentRequestItem.payment_request_id.in_(request_ids)))
        await session.execute(delete(PaymentRequest).where(PaymentRequest.order_id.in_(order_ids)))
        await session.execute(delete(Product).where(Product.order_id.in_(order_ids)))
        await session.execute(delete(Order).where(Order.client_id == client_id))
        await session.execute(delete(Client).where(Client.id == client_id))
        await session.execute(delete(Supplier).where(Supplier.id == supplier_id))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_partial_payments_decrease_remaining():
    client, supplier, owner, other, observer, order, product, request = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_payment(
                order.id,
                request.id,
                PaymentCreate(amount=Decimal("20.00"), currency="USD", exchange_rate=Decimal("1")),
                owner,
                session,
            )
            assert created.amount == Decimal("20.00")
            assert created.author_name == "Owner Manager"

        async with async_session_factory() as session:
            fetched = await get_payment_request(order.id, request.id, owner, session)
            assert fetched.paid_amount == Decimal("20.00")
            assert fetched.remaining_amount == Decimal("30.00")

        async with async_session_factory() as session:
            await create_payment(
                order.id,
                request.id,
                PaymentCreate(amount=Decimal("30.00"), currency="USD", exchange_rate=Decimal("1")),
                owner,
                session,
            )

        async with async_session_factory() as session:
            fetched = await get_payment_request(order.id, request.id, owner, session)
            assert fetched.paid_amount == Decimal("50.00")
            assert fetched.remaining_amount == Decimal("0.00")

        async with async_session_factory() as session:
            payments = await list_payments(order.id, request.id, owner, session)
            assert len(payments) == 2
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id])


@pytest.mark.asyncio
async def test_payment_in_different_currency_converted_via_exchange_rate():
    client, supplier, owner, other, observer, order, product, request = await _setup()
    try:
        async with async_session_factory() as session:
            # 140 CNY at "1 USD = 7 CNY" = 20 USD applied toward a USD-denominated request
            await create_payment(
                order.id,
                request.id,
                PaymentCreate(amount=Decimal("140.00"), currency="CNY", exchange_rate=Decimal("7.000000")),
                owner,
                session,
            )

        async with async_session_factory() as session:
            fetched = await get_payment_request(order.id, request.id, owner, session)
            assert fetched.paid_amount == Decimal("140.00") / Decimal("7.000000")
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id])


@pytest.mark.asyncio
async def test_count_payment_request_dependencies_counts_payments_and_blocks_delete():
    client, supplier, owner, other, observer, order, product, request = await _setup()
    try:
        async with async_session_factory() as session:
            count = await count_payment_request_dependencies(session, request.id)
            assert count == 0

            await create_payment(
                order.id,
                request.id,
                PaymentCreate(amount=Decimal("10.00"), currency="USD", exchange_rate=Decimal("1")),
                owner,
                session,
            )

        async with async_session_factory() as session:
            count = await count_payment_request_dependencies(session, request.id)
            assert count == 1

            with pytest.raises(HTTPException) as exc_info:
                await delete_payment_request(order.id, request.id, owner, session)
            assert exc_info.value.status_code == 409

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await delete_order(order.id, owner, session)
            assert exc_info.value.status_code == 409
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id])


@pytest.mark.asyncio
async def test_manager_cannot_access_payments_on_other_managers_order():
    client, supplier, owner, other, observer, order, product, request = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await list_payments(order.id, request.id, other, session)
            assert exc_info.value.status_code == 404

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_payment(
                    order.id,
                    request.id,
                    PaymentCreate(amount=Decimal("5.00"), currency="USD", exchange_rate=Decimal("1")),
                    other,
                    session,
                )
            assert exc_info.value.status_code == 404
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id])


@pytest.mark.asyncio
async def test_payment_exceeding_remaining_balance_is_rejected():
    client, supplier, owner, other, observer, order, product, request = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_payment(
                    order.id,
                    request.id,
                    PaymentCreate(amount=Decimal("50000.00"), currency="USD", exchange_rate=Decimal("1")),
                    owner,
                    session,
                )
            assert exc_info.value.status_code == 422

        async with async_session_factory() as session:
            fetched = await get_payment_request(order.id, request.id, owner, session)
            assert fetched.paid_amount == Decimal("0.00")
            assert fetched.remaining_amount == Decimal("50.00")
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id])


@pytest.mark.asyncio
async def test_partial_payment_then_overpayment_of_remainder_is_rejected():
    client, supplier, owner, other, observer, order, product, request = await _setup()
    try:
        async with async_session_factory() as session:
            await create_payment(
                order.id,
                request.id,
                PaymentCreate(amount=Decimal("20.00"), currency="USD", exchange_rate=Decimal("1")),
                owner,
                session,
            )

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_payment(
                    order.id,
                    request.id,
                    PaymentCreate(amount=Decimal("30.01"), currency="USD", exchange_rate=Decimal("1")),
                    owner,
                    session,
                )
            assert exc_info.value.status_code == 422

        async with async_session_factory() as session:
            fetched = await get_payment_request(order.id, request.id, owner, session)
            assert fetched.paid_amount == Decimal("20.00")
            assert fetched.remaining_amount == Decimal("30.00")
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id])


@pytest.mark.asyncio
async def test_observer_can_read_but_not_create_payment():
    client, supplier, owner, other, observer, order, product, request = await _setup()
    try:
        async with async_session_factory() as session:
            await create_payment(
                order.id,
                request.id,
                PaymentCreate(amount=Decimal("5.00"), currency="USD", exchange_rate=Decimal("1")),
                owner,
                session,
            )

        async with async_session_factory() as session:
            payments = await list_payments(order.id, request.id, observer, session)
            assert len(payments) == 1

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_payment(
                    order.id,
                    request.id,
                    PaymentCreate(amount=Decimal("5.00"), currency="USD", exchange_rate=Decimal("1")),
                    observer,
                    session,
                )
            assert exc_info.value.status_code == 403
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id])
