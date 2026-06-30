from decimal import Decimal

import pytest
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.models.client import Client
from app.models.order import Order, OrderStatus
from app.models.payment_request import PaymentRequest, PaymentRequestItem
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.services.payment_request_validation import (
    PaymentRequestValidationError,
    get_product_remaining,
    validate_payment_request_items,
)


async def _setup():
    async with async_session_factory() as session:
        client = Client(code="TSTPRV", full_name="Payment Request Validation Client")
        supplier = Supplier(name="Payment Request Validation Supplier")
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

        usd_product = Product(
            order_id=order.id,
            supplier_id=supplier.id,
            name="USD Widget",
            quantity=Decimal("10"),
            price=Decimal("5.00"),
            currency="USD",
        )
        cny_product = Product(
            order_id=order.id,
            supplier_id=supplier.id,
            name="CNY Widget",
            quantity=Decimal("4"),
            price=Decimal("20.00"),
            currency="CNY",
        )
        session.add_all([usd_product, cny_product])
        await session.commit()
        await session.refresh(usd_product)
        await session.refresh(cny_product)

        return client, supplier, admin, order, usd_product, cny_product


async def _cleanup(client_id: int, supplier_id: int):
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
        await session.commit()


@pytest.mark.asyncio
async def test_get_product_remaining_equals_total_with_no_existing_requests():
    client, supplier, admin, order, usd_product, cny_product = await _setup()
    try:
        async with async_session_factory() as session:
            remaining = await get_product_remaining(session, usd_product.id)
            assert remaining == Decimal("50.00")  # 10 * 5.00
    finally:
        await _cleanup(client.id, supplier.id)


@pytest.mark.asyncio
async def test_get_product_remaining_decreases_after_existing_item():
    client, supplier, admin, order, usd_product, cny_product = await _setup()
    try:
        async with async_session_factory() as session:
            request = PaymentRequest(order_id=order.id, created_by_id=admin.id)
            session.add(request)
            await session.commit()
            await session.refresh(request)

            session.add(PaymentRequestItem(payment_request_id=request.id, product_id=usd_product.id, amount=Decimal("20.00")))
            await session.commit()

        async with async_session_factory() as session:
            remaining = await get_product_remaining(session, usd_product.id)
            assert remaining == Decimal("30.00")
    finally:
        await _cleanup(client.id, supplier.id)


@pytest.mark.asyncio
async def test_validate_accepts_valid_single_currency_items():
    client, supplier, admin, order, usd_product, cny_product = await _setup()
    try:
        async with async_session_factory() as session:
            await validate_payment_request_items(session, [(usd_product.id, Decimal("50.00"))])
    finally:
        await _cleanup(client.id, supplier.id)


@pytest.mark.asyncio
async def test_validate_rejects_mixed_currencies():
    client, supplier, admin, order, usd_product, cny_product = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(PaymentRequestValidationError, match="same currency"):
                await validate_payment_request_items(
                    session, [(usd_product.id, Decimal("10.00")), (cny_product.id, Decimal("10.00"))]
                )
    finally:
        await _cleanup(client.id, supplier.id)


@pytest.mark.asyncio
async def test_validate_rejects_amount_exceeding_remaining():
    client, supplier, admin, order, usd_product, cny_product = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(PaymentRequestValidationError, match="exceeds remaining balance"):
                await validate_payment_request_items(session, [(usd_product.id, Decimal("999.00"))])
    finally:
        await _cleanup(client.id, supplier.id)


@pytest.mark.asyncio
async def test_validate_rejects_when_combined_with_existing_request_exceeds_remaining():
    client, supplier, admin, order, usd_product, cny_product = await _setup()
    try:
        async with async_session_factory() as session:
            request = PaymentRequest(order_id=order.id, created_by_id=admin.id)
            session.add(request)
            await session.commit()
            await session.refresh(request)

            session.add(PaymentRequestItem(payment_request_id=request.id, product_id=usd_product.id, amount=Decimal("40.00")))
            await session.commit()

        async with async_session_factory() as session:
            with pytest.raises(PaymentRequestValidationError, match="exceeds remaining balance"):
                await validate_payment_request_items(session, [(usd_product.id, Decimal("20.00"))])
    finally:
        await _cleanup(client.id, supplier.id)


@pytest.mark.asyncio
async def test_validate_exclude_request_id_allows_reediting_same_request():
    client, supplier, admin, order, usd_product, cny_product = await _setup()
    try:
        async with async_session_factory() as session:
            request = PaymentRequest(order_id=order.id, created_by_id=admin.id)
            session.add(request)
            await session.commit()
            await session.refresh(request)

            session.add(PaymentRequestItem(payment_request_id=request.id, product_id=usd_product.id, amount=Decimal("50.00")))
            await session.commit()

        async with async_session_factory() as session:
            # Re-saving the same request with the same total should not double-count its own items.
            await validate_payment_request_items(
                session, [(usd_product.id, Decimal("50.00"))], exclude_request_id=request.id
            )
    finally:
        await _cleanup(client.id, supplier.id)
