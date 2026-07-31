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
from app.routers.files import delete_file
from app.routers.orders import add_order_file
from app.schemas.order import OrderFileAdd
from app.services.storage import StorageError, storage


async def _setup():
    async with async_session_factory() as session:
        client = Client(code="TSTFILE", full_name="Files Test Client")
        supplier = Supplier(name="Files Test Supplier")
        admin = User(login="file_admin", password_hash=hash_password("x"), role=UserRole.admin, full_name="Admin")
        owner = User(login="file_owner", password_hash=hash_password("x"), role=UserRole.manager, full_name="Owner Manager")
        other = User(login="file_other", password_hash=hash_password("x"), role=UserRole.manager, full_name="Other Manager")
        observer = User(login="file_observer", password_hash=hash_password("x"), role=UserRole.observer, full_name="Observer")
        session.add_all([client, supplier, admin, owner, other, observer])
        await session.commit()
        for obj in (client, supplier, admin, owner, other, observer):
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

        photo_key = await storage.save("photo.jpg", b"fake image bytes")
        product = Product(
            order_id=order.id,
            supplier_id=supplier.id,
            name="Widget",
            quantity=Decimal("10"),
            price=Decimal("5.00"),
            currency="USD",
            photo_key=photo_key,
        )
        session.add(product)
        await session.commit()

        return client, supplier, admin, owner, other, observer, order, photo_key


async def _cleanup(client_id: int, supplier_id: int, user_ids: list[int]):
    async with async_session_factory() as session:
        order_ids = select(Order.id).where(Order.client_id == client_id)
        await session.execute(delete(Product).where(Product.order_id.in_(order_ids)))
        await session.execute(delete(Order).where(Order.client_id == client_id))
        await session.execute(delete(Client).where(Client.id == client_id))
        await session.execute(delete(Supplier).where(Supplier.id == supplier_id))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_observer_cannot_delete_file():
    client, supplier, admin, owner, other, observer, order, photo_key = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await delete_file(photo_key, observer, session)
            assert exc_info.value.status_code == 403

        # file must still be there
        assert await storage.get(photo_key) == b"fake image bytes"
    finally:
        await _cleanup(client.id, supplier.id, [admin.id, owner.id, other.id, observer.id])
        await storage.delete(photo_key)


@pytest.mark.asyncio
async def test_manager_cannot_delete_file_on_other_managers_order():
    client, supplier, admin, owner, other, observer, order, photo_key = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await delete_file(photo_key, other, session)
            assert exc_info.value.status_code == 404

        assert await storage.get(photo_key) == b"fake image bytes"
    finally:
        await _cleanup(client.id, supplier.id, [admin.id, owner.id, other.id, observer.id])
        await storage.delete(photo_key)


@pytest.mark.asyncio
async def test_manager_can_delete_file_on_own_order():
    client, supplier, admin, owner, other, observer, order, photo_key = await _setup()
    try:
        async with async_session_factory() as session:
            await delete_file(photo_key, owner, session)

        with pytest.raises(StorageError, match="File not found"):
            await storage.get(photo_key)
    finally:
        await _cleanup(client.id, supplier.id, [admin.id, owner.id, other.id, observer.id])


@pytest.mark.asyncio
async def test_manager_cannot_delete_unattached_file():
    client, supplier, admin, owner, other, observer, order, photo_key = await _setup()
    orphan_key = await storage.save("orphan.pdf", b"orphan bytes")
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await delete_file(orphan_key, owner, session)
            assert exc_info.value.status_code == 404

        assert await storage.get(orphan_key) == b"orphan bytes"
    finally:
        await _cleanup(client.id, supplier.id, [admin.id, owner.id, other.id, observer.id])
        await storage.delete(photo_key)
        await storage.delete(orphan_key)


@pytest.mark.asyncio
async def test_admin_can_delete_unattached_file():
    client, supplier, admin, owner, other, observer, order, photo_key = await _setup()
    orphan_key = await storage.save("orphan.pdf", b"orphan bytes")
    try:
        async with async_session_factory() as session:
            await delete_file(orphan_key, admin, session)

        with pytest.raises(StorageError, match="File not found"):
            await storage.get(orphan_key)
    finally:
        await _cleanup(client.id, supplier.id, [admin.id, owner.id, other.id, observer.id])
        await storage.delete(photo_key)


@pytest.mark.asyncio
async def test_manager_can_delete_order_level_file_on_own_order():
    client, supplier, admin, owner, other, observer, order, photo_key = await _setup()
    order_file_key = await storage.save("contract.pdf", b"order file bytes")
    try:
        async with async_session_factory() as session:
            await add_order_file(order.id, OrderFileAdd(file_key=order_file_key), owner, session)

        async with async_session_factory() as session:
            await delete_file(order_file_key, owner, session)

        with pytest.raises(StorageError, match="File not found"):
            await storage.get(order_file_key)
    finally:
        await _cleanup(client.id, supplier.id, [admin.id, owner.id, other.id, observer.id])
        await storage.delete(photo_key)
