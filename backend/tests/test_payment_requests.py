from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.models.client import Client
from app.models.order import Order, OrderStatus
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest, PaymentRequestItem, PaymentRequestPriority
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.routers.orders import delete_order
from app.routers.payment_requests_global import list_all_payment_requests
from app.routers.products import delete_product
from app.services.order_dependencies import count_order_dependencies
from app.services.product_dependencies import count_product_dependencies


async def _setup():
    async with async_session_factory() as session:
        client = Client(code="TSTPRQ", full_name="Payment Request Test Client")
        supplier = Supplier(name="Payment Request Test Supplier")
        session.add_all([client, supplier])
        await session.commit()
        await session.refresh(client)
        await session.refresh(supplier)

        admin = (await session.execute(select(User).where(User.role == UserRole.admin).limit(1))).scalar_one()

        order = Order(
            number=f"{client.code}-1",
            client_id=client.id,
            manager_id=admin.id,
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

        return client, supplier, admin, order, product


async def _cleanup(client_id: int, supplier_id: int):
    async with async_session_factory() as session:
        order_ids = select(Order.id).where(Order.client_id == client_id)
        await session.execute(
            delete(Payment).where(
                Payment.payment_request_id.in_(
                    select(PaymentRequest.id).where(PaymentRequest.order_id.in_(order_ids))
                )
            )
        )
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
        await session.commit()


@pytest.mark.asyncio
async def test_payment_request_with_item_persists():
    client, supplier, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            request = PaymentRequest(
                order_id=order.id,
                created_by_id=admin.id,
                requisites="bank details",
                details="urgent purchase",
                priority=PaymentRequestPriority.urgent,
                file_keys=["a.pdf", "b.pdf"],
            )
            session.add(request)
            await session.commit()
            await session.refresh(request)

            item = PaymentRequestItem(payment_request_id=request.id, product_id=product.id, amount=Decimal("25.00"))
            session.add(item)
            await session.commit()
            await session.refresh(item)

            assert request.priority == PaymentRequestPriority.urgent
            assert request.file_keys == ["a.pdf", "b.pdf"]
            assert item.amount == Decimal("25.00")
    finally:
        await _cleanup(client.id, supplier.id)


@pytest.mark.asyncio
async def test_deleting_payment_request_cascades_to_items():
    client, supplier, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            request = PaymentRequest(order_id=order.id, created_by_id=admin.id)
            session.add(request)
            await session.commit()
            await session.refresh(request)

            item = PaymentRequestItem(payment_request_id=request.id, product_id=product.id, amount=Decimal("10.00"))
            session.add(item)
            await session.commit()

            await session.delete(request)
            await session.commit()

        async with async_session_factory() as session:
            remaining = (
                await session.execute(select(PaymentRequestItem).where(PaymentRequestItem.payment_request_id == request.id))
            ).scalars().all()
            assert remaining == []
    finally:
        await _cleanup(client.id, supplier.id)


@pytest.mark.asyncio
async def test_count_order_dependencies_counts_payment_requests():
    client, supplier, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            count = await count_order_dependencies(session, order.id)
            assert count == 0  # a bare product doesn't block deletion (ТЗ §6)

            session.add(PaymentRequest(order_id=order.id, created_by_id=admin.id))
            await session.commit()

        async with async_session_factory() as session:
            count = await count_order_dependencies(session, order.id)
            assert count == 1  # payment request
    finally:
        await _cleanup(client.id, supplier.id)


@pytest.mark.asyncio
async def test_count_product_dependencies_counts_payment_request_items():
    client, supplier, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            count = await count_product_dependencies(session, product.id)
            assert count == 0

            request = PaymentRequest(order_id=order.id, created_by_id=admin.id)
            session.add(request)
            await session.commit()
            await session.refresh(request)

            session.add(PaymentRequestItem(payment_request_id=request.id, product_id=product.id, amount=Decimal("5.00")))
            await session.commit()

        async with async_session_factory() as session:
            count = await count_product_dependencies(session, product.id)
            assert count == 1
    finally:
        await _cleanup(client.id, supplier.id)


@pytest.mark.asyncio
async def test_delete_order_blocked_when_payment_request_exists():
    client, supplier, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            await session.execute(delete(Product).where(Product.id == product.id))
            session.add(PaymentRequest(order_id=order.id, created_by_id=admin.id))
            await session.commit()

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await delete_order(order.id, admin, session)
            assert exc_info.value.status_code == 409
    finally:
        await _cleanup(client.id, supplier.id)


@pytest.mark.asyncio
async def test_delete_product_blocked_when_referenced_by_payment_request_item():
    client, supplier, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            request = PaymentRequest(order_id=order.id, created_by_id=admin.id)
            session.add(request)
            await session.commit()
            await session.refresh(request)

            session.add(PaymentRequestItem(payment_request_id=request.id, product_id=product.id, amount=Decimal("5.00")))
            await session.commit()

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await delete_product(order.id, product.id, admin, session)
            assert exc_info.value.status_code == 409
    finally:
        await _cleanup(client.id, supplier.id)


@pytest.mark.asyncio
async def test_all_payment_requests_hides_settled_requests_by_default():
    """The payments page is a worklist, so a fully paid request only shows on demand."""
    client, supplier, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            open_req = PaymentRequest(order_id=order.id, created_by_id=admin.id)
            settled_req = PaymentRequest(order_id=order.id, created_by_id=admin.id)
            session.add_all([open_req, settled_req])
            await session.commit()
            await session.refresh(open_req)
            await session.refresh(settled_req)

            session.add_all([
                PaymentRequestItem(payment_request_id=open_req.id, product_id=product.id, amount=Decimal("25.00")),
                PaymentRequestItem(payment_request_id=settled_req.id, product_id=product.id, amount=Decimal("25.00")),
                Payment(payment_request_id=settled_req.id, author_id=admin.id, amount=Decimal("25.00"),
                        currency="USD", exchange_rate=Decimal("1")),
            ])
            await session.commit()

        # Every parameter is passed explicitly: called outside FastAPI, the Query()
        # defaults would arrive as Query objects rather than their values.
        async with async_session_factory() as session:
            default = await list_all_payment_requests(
                manager_id=None, client_id=None, search=None, sort="desc",
                remaining="positive", user=admin, session=session,
            )
            ids = {r.id for r in default}
            assert open_req.id in ids
            assert settled_req.id not in ids

        async with async_session_factory() as session:
            everything = await list_all_payment_requests(
                manager_id=None, client_id=None, search=None, sort="desc",
                remaining="all", user=admin, session=session,
            )
            assert {open_req.id, settled_req.id} <= {r.id for r in everything}
    finally:
        await _cleanup(client.id, supplier.id)
