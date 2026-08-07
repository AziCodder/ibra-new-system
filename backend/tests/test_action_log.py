from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.action_log import ActionLog
from app.models.client import Client
from app.models.logistics import Logistics, LogisticsStatus
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.routers.action_log import list_action_log
from app.routers.logistics import accept_logistics
from app.routers.orders import OrderStatusIn, create_order, set_order_status
from app.schemas.logistics import LogisticsAccept
from app.schemas.order import OrderCreate
from app.services.action_log import log_action
from tests.helpers import add_shipment

SHIP_DATE = datetime.now(UTC)

CLIENT_CODE = "TSTACT"
USER_LOGINS = ["act_admin", "act_manager"]
SUPPLIER_NAME = "Action Log Supplier"


async def _purge():
    async with async_session_factory() as session:
        client_ids = select(Client.id).where(Client.code == CLIENT_CODE)
        order_ids = select(Order.id).where(Order.client_id.in_(client_ids))
        user_ids = select(User.id).where(User.login.in_(USER_LOGINS))
        # action_logs reference users (FK) and the orders/logistics we create.
        await session.execute(delete(ActionLog).where(ActionLog.actor_id.in_(user_ids)))
        await session.execute(delete(Logistics).where(Logistics.order_id.in_(order_ids)))
        await session.execute(delete(Product).where(Product.order_id.in_(order_ids)))
        await session.execute(delete(Order).where(Order.client_id.in_(client_ids)))
        await session.execute(delete(Client).where(Client.code == CLIENT_CODE))
        await session.execute(delete(Supplier).where(Supplier.name == SUPPLIER_NAME))
        await session.execute(delete(User).where(User.login.in_(USER_LOGINS)))
        await session.commit()


async def _setup():
    await _purge()
    async with async_session_factory() as session:
        client = Client(code=CLIENT_CODE, full_name="Action Log Client")
        supplier = Supplier(name=SUPPLIER_NAME)
        admin = User(login="act_admin", password_hash=hash_password("x"), role=UserRole.admin, full_name="Act Admin")
        manager = User(
            login="act_manager", password_hash=hash_password("x"), role=UserRole.manager, full_name="Act Manager"
        )
        session.add_all([client, supplier, admin, manager])
        await session.commit()
        for obj in (client, supplier, admin, manager):
            await session.refresh(obj)
        return client, supplier, admin, manager


async def _logs_for(actor_id: int) -> list[ActionLog]:
    async with async_session_factory() as session:
        return list(
            (await session.execute(select(ActionLog).where(ActionLog.actor_id == actor_id))).scalars().all()
        )


@pytest.mark.asyncio
async def test_log_action_persists_row():
    client, supplier, admin, manager = await _setup()
    try:
        async with async_session_factory() as session:
            await log_action(session, admin, "order.created", "order", 12345, "details here")
            await session.commit()

        rows = await _logs_for(admin.id)
        assert len(rows) == 1
        assert rows[0].action == "order.created"
        assert rows[0].entity_type == "order"
        assert rows[0].entity_id == 12345
        assert rows[0].details == "details here"
    finally:
        await _purge()


@pytest.mark.asyncio
async def test_create_order_writes_action_log():
    client, supplier, admin, manager = await _setup()
    try:
        async with async_session_factory() as session:
            out = await create_order(
                OrderCreate(client_id=client.id, currency="USD", details="first"), manager, session
            )

        rows = await _logs_for(manager.id)
        created = [r for r in rows if r.action == "order.created" and r.entity_id == out.id]
        assert len(created) == 1
        assert created[0].entity_type == "order"
    finally:
        await _purge()


@pytest.mark.asyncio
async def test_set_order_status_writes_action_log():
    client, supplier, admin, manager = await _setup()
    try:
        async with async_session_factory() as session:
            order = Order(
                number=f"{client.code}-1",
                client_id=client.id,
                manager_id=manager.id,
                status=OrderStatus.in_progress,
                currency="USD",
            )
            session.add(order)
            await session.commit()
            await session.refresh(order)
            order_id = order.id

        async with async_session_factory() as session:
            await set_order_status(order_id, OrderStatusIn(status=OrderStatus.cancelled), manager, session)

        rows = await _logs_for(manager.id)
        changed = [r for r in rows if r.action == "order.status_changed" and r.entity_id == order_id]
        assert len(changed) == 1
        assert "in_progress" in changed[0].details
        assert "cancelled" in changed[0].details
    finally:
        await _purge()


@pytest.mark.asyncio
async def test_accept_logistics_writes_action_log():
    client, supplier, admin, manager = await _setup()
    try:
        async with async_session_factory() as session:
            order = Order(
                number=f"{client.code}-2",
                client_id=client.id,
                manager_id=manager.id,
                status=OrderStatus.in_progress,
                currency="USD",
            )
            session.add(order)
            await session.commit()
            await session.refresh(order)

            product = Product(
                order_id=order.id, supplier_id=supplier.id, name="Widget",
                quantity=Decimal("10"), price=Decimal("5.00"), currency="USD",
            )
            session.add(product)
            await session.commit()
            await session.refresh(product)

            logistics = await add_shipment(
                            session,
                            lines=[(product.id, Decimal("5"))],
                            order_id=order.id,
                            created_by_id=manager.id,
                            tracking="TRK",
                            ship_date=SHIP_DATE,
                            status=LogisticsStatus.in_transit,
                        )
            await session.commit()
            await session.refresh(logistics)
            order_id, logistics_id = order.id, logistics.id

        async with async_session_factory() as session:
            await accept_logistics(
                order_id,
                logistics_id,
                LogisticsAccept(
                    received_date=SHIP_DATE, expense_amount=Decimal("100.00"),
                    currency="USD", exchange_rate=Decimal("1.0"),
                ),
                admin,
                session,
            )

        rows = await _logs_for(admin.id)
        accepted = [r for r in rows if r.action == "logistics.accepted" and r.entity_id == logistics_id]
        assert len(accepted) == 1
        assert accepted[0].entity_type == "logistics"
    finally:
        await _purge()


@pytest.mark.asyncio
async def test_list_action_log_admin_filters_by_entity_type():
    client, supplier, admin, manager = await _setup()
    try:
        async with async_session_factory() as session:
            await log_action(session, admin, "order.created", "order", 1, "")
            await log_action(session, admin, "logistics.accepted", "logistics", 2, "")
            await session.commit()

        async with async_session_factory() as session:
            all_rows = await list_action_log(
                entity_type=None, actor_id=admin.id, limit=100, _admin=admin, session=session
            )
            assert len(all_rows) == 2
            assert all_rows[0].actor_name == "Act Admin"  # joined author name

        async with async_session_factory() as session:
            only_logistics = await list_action_log(
                entity_type="logistics", actor_id=admin.id, limit=100, _admin=admin, session=session
            )
            assert len(only_logistics) == 1
            assert only_logistics[0].action == "logistics.accepted"
    finally:
        await _purge()
