from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.client import Client
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.routers.products import create_product, delete_product, list_products, update_product
from app.schemas.product import ProductCreate, ProductUpdate


async def _setup():
    async with async_session_factory() as session:
        client = Client(code="TSTPR", full_name="Products Test Client")
        session.add(client)

        owner = User(login="prod_owner", password_hash=hash_password("x"), role=UserRole.manager, full_name="Owner Manager")
        other = User(login="prod_other", password_hash=hash_password("x"), role=UserRole.manager, full_name="Other Manager")
        observer = User(login="prod_observer", password_hash=hash_password("x"), role=UserRole.observer, full_name="Observer")
        supplier = Supplier(name="Products Test Supplier")
        session.add_all([owner, other, observer, supplier])
        await session.commit()
        for obj in (client, owner, other, observer, supplier):
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
        return client, owner, other, observer, supplier, order


async def _cleanup(client_id: int, user_ids: list[int], supplier_id: int):
    async with async_session_factory() as session:
        await session.execute(
            delete(Product).where(Product.order_id.in_(select(Order.id).where(Order.client_id == client_id)))
        )
        await session.execute(delete(Order).where(Order.client_id == client_id))
        await session.execute(delete(Client).where(Client.id == client_id))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.execute(delete(Supplier).where(Supplier.id == supplier_id))
        await session.commit()


@pytest.mark.asyncio
async def test_create_update_delete_product_lifecycle():
    client, owner, other, observer, supplier, order = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_product(
                order.id,
                ProductCreate(supplier_id=supplier.id, name="Widget", quantity=Decimal("3"), price=Decimal("12.50")),
                owner,
                session,
            )
            assert created.name == "Widget"
            assert created.quantity == Decimal("3")
            assert created.supplier_name == "Products Test Supplier"

        async with async_session_factory() as session:
            updated = await update_product(
                order.id, created.id, ProductUpdate(price=Decimal("15.00"), quantity=Decimal("5")), owner, session
            )
            assert updated.price == Decimal("15.00")
            assert updated.quantity == Decimal("5")
            assert updated.name == "Widget"

        async with async_session_factory() as session:
            await delete_product(order.id, created.id, owner, session)

        async with async_session_factory() as session:
            products = await list_products(order.id, owner, session)
            assert products == []
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id], supplier.id)


@pytest.mark.asyncio
async def test_manager_cannot_crud_products_on_other_managers_order():
    client, owner, other, observer, supplier, order = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await list_products(order.id, other, session)
            assert exc_info.value.status_code == 404

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_product(
                    order.id,
                    ProductCreate(supplier_id=supplier.id, name="Widget", quantity=Decimal("1"), price=Decimal("1")),
                    other,
                    session,
                )
            assert exc_info.value.status_code == 404
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id], supplier.id)


@pytest.mark.asyncio
async def test_observer_can_read_but_not_write_products():
    client, owner, other, observer, supplier, order = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_product(
                order.id,
                ProductCreate(supplier_id=supplier.id, name="Widget", quantity=Decimal("1"), price=Decimal("1")),
                owner,
                session,
            )

        async with async_session_factory() as session:
            products = await list_products(order.id, observer, session)
            assert len(products) == 1

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_product(
                    order.id,
                    ProductCreate(supplier_id=supplier.id, name="Gadget", quantity=Decimal("1"), price=Decimal("1")),
                    observer,
                    session,
                )
            assert exc_info.value.status_code == 403

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await update_product(order.id, created.id, ProductUpdate(name="Changed"), observer, session)
            assert exc_info.value.status_code == 403

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await delete_product(order.id, created.id, observer, session)
            assert exc_info.value.status_code == 403
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id], supplier.id)
