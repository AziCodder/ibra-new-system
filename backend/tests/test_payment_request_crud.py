from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.client import Client
from app.models.order import Order, OrderStatus
from app.models.payment_request import PaymentRequest, PaymentRequestItem, PaymentRequestPriority
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.routers.payment_requests import (
    create_payment_request,
    delete_payment_request,
    get_payment_request,
    list_payment_requests,
    update_payment_request,
)
from app.schemas.payment_request import PaymentRequestCreate, PaymentRequestItemIn, PaymentRequestUpdate


async def _setup():
    async with async_session_factory() as session:
        client = Client(code="TSTPRC", full_name="Payment Request CRUD Client")
        supplier = Supplier(name="Payment Request CRUD Supplier")
        owner = User(login="prc_owner", password_hash=hash_password("x"), role=UserRole.manager, full_name="Owner Manager")
        other = User(login="prc_other", password_hash=hash_password("x"), role=UserRole.manager, full_name="Other Manager")
        observer = User(login="prc_observer", password_hash=hash_password("x"), role=UserRole.observer, full_name="Observer")
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

        return client, supplier, owner, other, observer, order, usd_product, cny_product


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
async def test_create_list_get_update_delete_lifecycle():
    client, supplier, owner, other, observer, order, usd_product, cny_product = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_payment_request(
                order.id,
                PaymentRequestCreate(
                    requisites="bank details",
                    details="purchase",
                    priority=PaymentRequestPriority.urgent,
                    items=[PaymentRequestItemIn(product_id=usd_product.id, amount=Decimal("20.00"))],
                ),
                owner,
                session,
            )
            assert created.total_amount == Decimal("20.00")
            assert created.currency == "USD"
            assert created.created_by_name == "Owner Manager"
            assert len(created.items) == 1

        async with async_session_factory() as session:
            listed = await list_payment_requests(order.id, owner, session)
            assert len(listed) == 1

        async with async_session_factory() as session:
            fetched = await get_payment_request(order.id, created.id, owner, session)
            assert fetched.requisites == "bank details"

        async with async_session_factory() as session:
            updated = await update_payment_request(
                order.id,
                created.id,
                PaymentRequestUpdate(
                    requisites="updated details",
                    items=[PaymentRequestItemIn(product_id=usd_product.id, amount=Decimal("30.00"))],
                ),
                owner,
                session,
            )
            assert updated.requisites == "updated details"
            assert updated.total_amount == Decimal("30.00")

        async with async_session_factory() as session:
            await delete_payment_request(order.id, created.id, owner, session)

        async with async_session_factory() as session:
            listed = await list_payment_requests(order.id, owner, session)
            assert listed == []
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id])


@pytest.mark.asyncio
async def test_create_rejects_mixed_currency_items_with_422():
    client, supplier, owner, other, observer, order, usd_product, cny_product = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_payment_request(
                    order.id,
                    PaymentRequestCreate(
                        items=[
                            PaymentRequestItemIn(product_id=usd_product.id, amount=Decimal("10.00")),
                            PaymentRequestItemIn(product_id=cny_product.id, amount=Decimal("10.00")),
                        ]
                    ),
                    owner,
                    session,
                )
            assert exc_info.value.status_code == 422
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id])


@pytest.mark.asyncio
async def test_create_rejects_amount_exceeding_remaining_with_422():
    client, supplier, owner, other, observer, order, usd_product, cny_product = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_payment_request(
                    order.id,
                    PaymentRequestCreate(items=[PaymentRequestItemIn(product_id=usd_product.id, amount=Decimal("999.00"))]),
                    owner,
                    session,
                )
            assert exc_info.value.status_code == 422
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id])


@pytest.mark.asyncio
async def test_create_rejects_product_from_another_order_with_422():
    client, supplier, owner, other, observer, order, usd_product, cny_product = await _setup()
    try:
        async with async_session_factory() as session:
            foreign_order = Order(
                number="FOREIGN-1", client_id=client.id, manager_id=owner.id, status=OrderStatus.in_progress, currency="USD"
            )
            session.add(foreign_order)
            await session.commit()
            await session.refresh(foreign_order)

            with pytest.raises(HTTPException) as exc_info:
                await create_payment_request(
                    foreign_order.id,
                    PaymentRequestCreate(items=[PaymentRequestItemIn(product_id=usd_product.id, amount=Decimal("5.00"))]),
                    owner,
                    session,
                )
            assert exc_info.value.status_code == 422

            await session.execute(delete(Order).where(Order.id == foreign_order.id))
            await session.commit()
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id])


@pytest.mark.asyncio
async def test_manager_cannot_access_other_managers_payment_requests():
    client, supplier, owner, other, observer, order, usd_product, cny_product = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await list_payment_requests(order.id, other, session)
            assert exc_info.value.status_code == 404

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_payment_request(
                    order.id,
                    PaymentRequestCreate(items=[PaymentRequestItemIn(product_id=usd_product.id, amount=Decimal("5.00"))]),
                    other,
                    session,
                )
            assert exc_info.value.status_code == 404
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id])


@pytest.mark.asyncio
async def test_observer_can_read_but_not_create():
    client, supplier, owner, other, observer, order, usd_product, cny_product = await _setup()
    try:
        async with async_session_factory() as session:
            await create_payment_request(
                order.id,
                PaymentRequestCreate(items=[PaymentRequestItemIn(product_id=usd_product.id, amount=Decimal("5.00"))]),
                owner,
                session,
            )

        async with async_session_factory() as session:
            listed = await list_payment_requests(order.id, observer, session)
            assert len(listed) == 1

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_payment_request(
                    order.id,
                    PaymentRequestCreate(items=[PaymentRequestItemIn(product_id=usd_product.id, amount=Decimal("5.00"))]),
                    observer,
                    session,
                )
            assert exc_info.value.status_code == 403
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id])


def test_schema_rejects_more_than_three_files():
    with pytest.raises(ValidationError):
        PaymentRequestCreate(
            file_keys=["a.pdf", "b.pdf", "c.pdf", "d.pdf"],
            items=[PaymentRequestItemIn(product_id=1, amount=Decimal("1.00"))],
        )


def test_schema_rejects_empty_items():
    with pytest.raises(ValidationError):
        PaymentRequestCreate(items=[])
