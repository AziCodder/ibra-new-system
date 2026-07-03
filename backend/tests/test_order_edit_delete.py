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
from app.routers.orders import create_order, delete_order
from app.schemas.order import OrderCreate
from app.services.order_dependencies import count_order_dependencies


async def _setup_order():
    async with async_session_factory() as session:
        client = Client(code="TSTED", full_name="Edit/Delete Test Client")
        session.add(client)
        await session.commit()
        await session.refresh(client)

        manager_result = await session.execute(select(User).where(User.role == UserRole.admin).limit(1))
        manager = manager_result.scalar_one()

        order = Order(
            number=f"{client.code}-1",
            client_id=client.id,
            manager_id=manager.id,
            status=OrderStatus.in_progress,
            currency="USD",
            details="original details",
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)
        return client, order


async def _cleanup(client_id: int):
    async with async_session_factory() as session:
        await session.execute(
            delete(Product).where(Product.order_id.in_(select(Order.id).where(Order.client_id == client_id)))
        )
        await session.execute(delete(Order).where(Order.client_id == client_id))
        await session.execute(delete(Client).where(Client.id == client_id))
        await session.commit()


@pytest.mark.asyncio
async def test_count_order_dependencies_is_zero_with_no_related_entities():
    client, order = await _setup_order()
    try:
        async with async_session_factory() as session:
            count = await count_order_dependencies(session, order.id)
            assert count == 0
    finally:
        await _cleanup(client.id)


@pytest.mark.asyncio
async def test_update_order_details_persists():
    client, order = await _setup_order()
    try:
        async with async_session_factory() as session:
            result = await session.execute(select(Order).where(Order.id == order.id))
            fetched = result.scalar_one()
            fetched.details = "updated details"
            await session.commit()

        async with async_session_factory() as session:
            result = await session.execute(select(Order).where(Order.id == order.id))
            reread = result.scalar_one()
            assert reread.details == "updated details"
    finally:
        await _cleanup(client.id)


@pytest.mark.asyncio
async def test_delete_order_with_no_dependencies_removes_row():
    client, order = await _setup_order()
    try:
        async with async_session_factory() as session:
            dependency_count = await count_order_dependencies(session, order.id)
            assert dependency_count == 0

            result = await session.execute(select(Order).where(Order.id == order.id))
            to_delete = result.scalar_one()
            await session.delete(to_delete)
            await session.commit()

        async with async_session_factory() as session:
            result = await session.execute(select(Order).where(Order.id == order.id))
            assert result.scalar_one_or_none() is None
    finally:
        await _cleanup(client.id)


@pytest.mark.asyncio
async def test_count_order_dependencies_counts_products():
    client, order = await _setup_order()
    try:
        async with async_session_factory() as session:
            supplier = Supplier(name="Dependency Test Supplier")
            session.add(supplier)
            await session.commit()
            await session.refresh(supplier)

            session.add(
                Product(
                    order_id=order.id,
                    supplier_id=supplier.id,
                    name="Widget",
                    quantity=Decimal("2"),
                    price=Decimal("10.50"),
                    currency="USD",
                )
            )
            await session.commit()

        async with async_session_factory() as session:
            count = await count_order_dependencies(session, order.id)
            assert count == 1
    finally:
        await _cleanup(client.id)
        async with async_session_factory() as session:
            await session.execute(delete(Supplier).where(Supplier.name == "Dependency Test Supplier"))
            await session.commit()


@pytest.mark.asyncio
async def test_delete_order_blocked_when_products_exist():
    client, order = await _setup_order()
    try:
        async with async_session_factory() as session:
            supplier = Supplier(name="Blocked Delete Supplier")
            session.add(supplier)
            await session.commit()
            await session.refresh(supplier)

            session.add(
                Product(
                    order_id=order.id,
                    supplier_id=supplier.id,
                    name="Widget",
                    quantity=Decimal("1"),
                    price=Decimal("5.00"),
                    currency="USD",
                )
            )
            await session.commit()

        async with async_session_factory() as session:
            admin_result = await session.execute(select(User).where(User.role == UserRole.admin).limit(1))
            admin = admin_result.scalar_one()
            with pytest.raises(HTTPException) as exc_info:
                await delete_order(order.id, admin, session)
            assert exc_info.value.status_code == 409
    finally:
        await _cleanup(client.id)
        async with async_session_factory() as session:
            await session.execute(delete(Supplier).where(Supplier.name == "Blocked Delete Supplier"))
            await session.commit()


@pytest.mark.asyncio
async def test_observer_cannot_create_order():
    async with async_session_factory() as session:
        client = Client(code="TSTOBSC", full_name="Observer Create Client")
        observer = User(
            login="obscreate_obs", password_hash=hash_password("x"),
            role=UserRole.observer, full_name="Observer",
        )
        session.add_all([client, observer])
        await session.commit()
        await session.refresh(client)
        await session.refresh(observer)
        client_id, observer_id = client.id, observer.id
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_order(
                    OrderCreate(client_id=client_id, currency="USD", details=""), observer, session
                )
            assert exc_info.value.status_code == 403
        # No order row was created for this client.
        async with async_session_factory() as session:
            leftover = await session.execute(select(Order).where(Order.client_id == client_id))
            assert leftover.scalar_one_or_none() is None
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(Order).where(Order.client_id == client_id))
            await session.execute(delete(Client).where(Client.id == client_id))
            await session.execute(delete(User).where(User.id == observer_id))
            await session.commit()
