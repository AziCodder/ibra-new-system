from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.client import Client
from app.models.logistics import Logistics, LogisticsStatus
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.routers.logistics_global import list_all_logistics
from tests.helpers import add_shipment

SHIP_DATE = datetime.now(UTC)


CLIENT_CODES = ["TSTLGA", "TSTLGB"]
USER_LOGINS = ["glg_owner", "glg_other", "glg_admin"]
SUPPLIER_NAME = "Global Logistics Supplier"


async def _purge():
    """Remove any leftover rows from a prior aborted run so unique codes/logins are free."""
    async with async_session_factory() as session:
        client_ids = select(Client.id).where(Client.code.in_(CLIENT_CODES))
        order_ids = select(Order.id).where(Order.client_id.in_(client_ids))
        await session.execute(delete(Logistics).where(Logistics.order_id.in_(order_ids)))
        await session.execute(delete(Product).where(Product.order_id.in_(order_ids)))
        await session.execute(delete(Order).where(Order.client_id.in_(client_ids)))
        await session.execute(delete(Client).where(Client.code.in_(CLIENT_CODES)))
        await session.execute(delete(Supplier).where(Supplier.name == SUPPLIER_NAME))
        await session.execute(delete(User).where(User.login.in_(USER_LOGINS)))
        await session.commit()


async def _setup():
    await _purge()
    async with async_session_factory() as session:
        client_a = Client(code="TSTLGA", full_name="Global Logistics Client A")
        client_b = Client(code="TSTLGB", full_name="Global Logistics Client B")
        supplier = Supplier(name="Global Logistics Supplier")
        owner = User(login="glg_owner", password_hash=hash_password("x"), role=UserRole.manager, full_name="Owner Manager")
        other = User(login="glg_other", password_hash=hash_password("x"), role=UserRole.manager, full_name="Other Manager")
        admin = User(login="glg_admin", password_hash=hash_password("x"), role=UserRole.admin, full_name="Admin")
        session.add_all([client_a, client_b, supplier, owner, other, admin])
        await session.commit()
        for obj in (client_a, client_b, supplier, owner, other, admin):
            await session.refresh(obj)

        order_a = Order(
            number=f"{client_a.code}-1", client_id=client_a.id, manager_id=owner.id,
            status=OrderStatus.in_progress, currency="USD",
        )
        order_b = Order(
            number=f"{client_b.code}-1", client_id=client_b.id, manager_id=other.id,
            status=OrderStatus.in_progress, currency="USD",
        )
        session.add_all([order_a, order_b])
        await session.commit()
        await session.refresh(order_a)
        await session.refresh(order_b)

        product_a = Product(
            order_id=order_a.id, supplier_id=supplier.id, name="Widget A",
            quantity=Decimal("20"), price=Decimal("5.00"), currency="USD",
        )
        product_b = Product(
            order_id=order_b.id, supplier_id=supplier.id, name="Widget B",
            quantity=Decimal("20"), price=Decimal("5.00"), currency="USD",
        )
        session.add_all([product_a, product_b])
        await session.commit()
        await session.refresh(product_a)
        await session.refresh(product_b)

        logistics_a = await add_shipment(
                          session,
                          lines=[(product_a.id, Decimal("10"))],
                          order_id=order_a.id,
                          created_by_id=owner.id,
                          tracking="TRACK-AAA",
                          ship_date=SHIP_DATE,
                          status=LogisticsStatus.in_transit,
                      )
        await session.commit()
        await session.refresh(logistics_a)

        # Separate commit so created_at (server_default now()) differs from logistics_a,
        # since Postgres now() is stable within a single transaction — needed for sort test.
        logistics_b = await add_shipment(
                          session,
                          lines=[(product_b.id, Decimal("5"))],
                          order_id=order_b.id,
                          created_by_id=other.id,
                          tracking="TRACK-BBB",
                          ship_date=SHIP_DATE + timedelta(hours=1),
                          status=LogisticsStatus.accepted,
                      )
        await session.commit()
        await session.refresh(logistics_b)

        return client_a, client_b, supplier, owner, other, admin, order_a, order_b, logistics_a, logistics_b


async def _cleanup(client_ids: list[int], supplier_id: int, user_ids: list[int]):
    async with async_session_factory() as session:
        order_ids = select(Order.id).where(Order.client_id.in_(client_ids))
        await session.execute(delete(Logistics).where(Logistics.order_id.in_(order_ids)))
        await session.execute(delete(Product).where(Product.order_id.in_(order_ids)))
        await session.execute(delete(Order).where(Order.client_id.in_(client_ids)))
        await session.execute(delete(Client).where(Client.id.in_(client_ids)))
        await session.execute(delete(Supplier).where(Supplier.id == supplier_id))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_admin_sees_all_logistics_across_orders():
    client_a, client_b, supplier, owner, other, admin, order_a, order_b, logistics_a, logistics_b = await _setup()
    try:
        async with async_session_factory() as session:
            items = await list_all_logistics(
                status=None, client_id=None, manager_id=None, search="TRACK-", sort="desc",
                user=admin, session=session,
            )
            trackings = {item.tracking for item in items}
            assert trackings == {"TRACK-AAA", "TRACK-BBB"}
            for item in items:
                if item.tracking == "TRACK-AAA":
                    assert item.order_number == order_a.number
                    assert item.client_name == client_a.full_name
                    assert item.manager_name == owner.full_name
    finally:
        await _cleanup([client_a.id, client_b.id], supplier.id, [owner.id, other.id, admin.id])


@pytest.mark.asyncio
async def test_manager_sees_only_own_orders_logistics():
    client_a, client_b, supplier, owner, other, admin, order_a, order_b, logistics_a, logistics_b = await _setup()
    try:
        async with async_session_factory() as session:
            owner_items = await list_all_logistics(
                status=None, client_id=None, manager_id=None, search=None, sort="desc",
                user=owner, session=session,
            )
            assert [item.tracking for item in owner_items] == ["TRACK-AAA"]

        async with async_session_factory() as session:
            other_items = await list_all_logistics(
                status=None, client_id=None, manager_id=None, search=None, sort="desc",
                user=other, session=session,
            )
            assert [item.tracking for item in other_items] == ["TRACK-BBB"]
    finally:
        await _cleanup([client_a.id, client_b.id], supplier.id, [owner.id, other.id, admin.id])


@pytest.mark.asyncio
async def test_filter_by_status():
    client_a, client_b, supplier, owner, other, admin, order_a, order_b, logistics_a, logistics_b = await _setup()
    try:
        async with async_session_factory() as session:
            items = await list_all_logistics(
                status=LogisticsStatus.accepted, client_id=None, manager_id=None, search="TRACK-", sort="desc",
                user=admin, session=session,
            )
            assert [item.tracking for item in items] == ["TRACK-BBB"]
    finally:
        await _cleanup([client_a.id, client_b.id], supplier.id, [owner.id, other.id, admin.id])


@pytest.mark.asyncio
async def test_filter_by_client_id():
    client_a, client_b, supplier, owner, other, admin, order_a, order_b, logistics_a, logistics_b = await _setup()
    try:
        async with async_session_factory() as session:
            items = await list_all_logistics(
                status=None, client_id=client_b.id, manager_id=None, search=None, sort="desc",
                user=admin, session=session,
            )
            assert [item.tracking for item in items] == ["TRACK-BBB"]
    finally:
        await _cleanup([client_a.id, client_b.id], supplier.id, [owner.id, other.id, admin.id])


@pytest.mark.asyncio
async def test_filter_by_manager_id():
    client_a, client_b, supplier, owner, other, admin, order_a, order_b, logistics_a, logistics_b = await _setup()
    try:
        async with async_session_factory() as session:
            items = await list_all_logistics(
                status=None, client_id=None, manager_id=owner.id, search=None, sort="desc",
                user=admin, session=session,
            )
            assert [item.tracking for item in items] == ["TRACK-AAA"]
    finally:
        await _cleanup([client_a.id, client_b.id], supplier.id, [owner.id, other.id, admin.id])


@pytest.mark.asyncio
async def test_search_matches_tracking_order_number_and_product_name():
    client_a, client_b, supplier, owner, other, admin, order_a, order_b, logistics_a, logistics_b = await _setup()
    try:
        async with async_session_factory() as session:
            by_tracking = await list_all_logistics(
                status=None, client_id=None, manager_id=None, search="TRACK-AAA", sort="desc",
                user=admin, session=session,
            )
            assert [item.tracking for item in by_tracking] == ["TRACK-AAA"]

        async with async_session_factory() as session:
            by_order_number = await list_all_logistics(
                status=None, client_id=None, manager_id=None, search=order_b.number, sort="desc",
                user=admin, session=session,
            )
            assert [item.tracking for item in by_order_number] == ["TRACK-BBB"]

        async with async_session_factory() as session:
            by_product_name = await list_all_logistics(
                status=None, client_id=None, manager_id=None, search="Widget B", sort="desc",
                user=admin, session=session,
            )
            assert [item.tracking for item in by_product_name] == ["TRACK-BBB"]
    finally:
        await _cleanup([client_a.id, client_b.id], supplier.id, [owner.id, other.id, admin.id])


@pytest.mark.asyncio
async def test_sort_by_created_at_asc_and_desc():
    client_a, client_b, supplier, owner, other, admin, order_a, order_b, logistics_a, logistics_b = await _setup()
    try:
        async with async_session_factory() as session:
            desc_items = await list_all_logistics(
                status=None, client_id=None, manager_id=None, search="TRACK-", sort="desc",
                user=admin, session=session,
            )
            assert [item.tracking for item in desc_items] == ["TRACK-BBB", "TRACK-AAA"]

        async with async_session_factory() as session:
            asc_items = await list_all_logistics(
                status=None, client_id=None, manager_id=None, search="TRACK-", sort="asc",
                user=admin, session=session,
            )
            assert [item.tracking for item in asc_items] == ["TRACK-AAA", "TRACK-BBB"]
    finally:
        await _cleanup([client_a.id, client_b.id], supplier.id, [owner.id, other.id, admin.id])
