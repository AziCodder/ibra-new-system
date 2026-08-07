from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.models.client import Client
from app.models.logistics import Logistics, LogisticsStatus
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.services.order_dependencies import count_order_dependencies
from app.services.product_dependencies import count_product_dependencies
from tests.helpers import add_shipment


async def _setup():
    async with async_session_factory() as session:
        client = Client(code="TSTLOG", full_name="Logistics Test Client")
        supplier = Supplier(name="Logistics Test Supplier")
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
            quantity=Decimal("20"),
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
        await session.execute(delete(Logistics).where(Logistics.order_id.in_(order_ids)))
        await session.execute(delete(Product).where(Product.order_id.in_(order_ids)))
        await session.execute(delete(Order).where(Order.client_id == client_id))
        await session.execute(delete(Client).where(Client.id == client_id))
        await session.execute(delete(Supplier).where(Supplier.id == supplier_id))
        await session.commit()


@pytest.mark.asyncio
async def test_logistics_persists_with_defaults():
    client, supplier, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            logistics = await add_shipment(
                            session,
                            lines=[(product.id, Decimal("10"))],
                            order_id=order.id,
                            created_by_id=admin.id,
                            tracking="M77-170566",
                            ship_date=datetime.now(UTC),
                        )
            await session.commit()
            await session.refresh(logistics)

            assert logistics.status == LogisticsStatus.in_transit
            assert logistics.received_date is None
            assert logistics.expense_amount is None
    finally:
        await _cleanup(client.id, supplier.id)


@pytest.mark.asyncio
async def test_count_order_dependencies_counts_logistics():
    client, supplier, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            count = await count_order_dependencies(session, order.id)
            assert count == 0  # a bare product doesn't block deletion (ТЗ §6)

            await add_shipment(
                    session,
                    lines=[(product.id, Decimal("10"))],
                    order_id=order.id,
                    created_by_id=admin.id,
                    ship_date=datetime.now(UTC),
                )
            await session.commit()

        async with async_session_factory() as session:
            count = await count_order_dependencies(session, order.id)
            assert count == 1  # logistics
    finally:
        await _cleanup(client.id, supplier.id)


@pytest.mark.asyncio
async def test_count_product_dependencies_counts_logistics():
    client, supplier, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            count = await count_product_dependencies(session, product.id)
            assert count == 0

            await add_shipment(
                    session,
                    lines=[(product.id, Decimal("10"))],
                    order_id=order.id,
                    created_by_id=admin.id,
                    ship_date=datetime.now(UTC),
                )
            await session.commit()

        async with async_session_factory() as session:
            count = await count_product_dependencies(session, product.id)
            assert count == 1
    finally:
        await _cleanup(client.id, supplier.id)
