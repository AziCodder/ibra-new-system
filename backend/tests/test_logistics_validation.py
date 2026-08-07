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
from app.services.logistics_validation import (
    LogisticsValidationError,
    get_product_shipped_remaining,
    validate_logistics_items,
)
from tests.helpers import add_shipment


async def _setup():
    async with async_session_factory() as session:
        client = Client(code="TSTLGV", full_name="Logistics Validation Client")
        supplier = Supplier(name="Logistics Validation Supplier")
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
async def test_get_product_shipped_remaining_equals_quantity_with_no_shipments():
    client, supplier, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            remaining = await get_product_shipped_remaining(session, product.id)
            assert remaining == Decimal("20")
    finally:
        await _cleanup(client.id, supplier.id)


@pytest.mark.asyncio
async def test_get_product_shipped_remaining_decreases_after_existing_shipment():
    client, supplier, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            await add_shipment(
                    session,
                    lines=[(product.id, Decimal("10"))],
                    order_id=order.id,
                    created_by_id=admin.id,
                    ship_date=datetime.now(UTC),
                )
            await session.commit()

        async with async_session_factory() as session:
            remaining = await get_product_shipped_remaining(session, product.id)
            assert remaining == Decimal("10")  # bought 20, shipped 10 -> 10 available
    finally:
        await _cleanup(client.id, supplier.id)


@pytest.mark.asyncio
async def test_validate_accepts_quantity_within_remaining():
    client, supplier, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            await add_shipment(
                    session,
                    lines=[(product.id, Decimal("10"))],
                    order_id=order.id,
                    created_by_id=admin.id,
                    ship_date=datetime.now(UTC),
                )
            await session.commit()

        async with async_session_factory() as session:
            await validate_logistics_items(
                session, [(product.id, Decimal("10"))]
            )
    finally:
        await _cleanup(client.id, supplier.id)


@pytest.mark.asyncio
async def test_validate_rejects_quantity_exceeding_remaining():
    client, supplier, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            await add_shipment(
                    session,
                    lines=[(product.id, Decimal("10"))],
                    order_id=order.id,
                    created_by_id=admin.id,
                    ship_date=datetime.now(UTC),
                )
            await session.commit()

        async with async_session_factory() as session:
            with pytest.raises(LogisticsValidationError, match="exceeds shipped remaining balance"):
                await validate_logistics_items(
                session, [(product.id, Decimal("11"))]
            )
    finally:
        await _cleanup(client.id, supplier.id)


@pytest.mark.asyncio
async def test_cancelled_shipment_excluded_from_shipped_total():
    client, supplier, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            await add_shipment(
                    session,
                    lines=[(product.id, Decimal("15"))],
                    order_id=order.id,
                    created_by_id=admin.id,
                    ship_date=datetime.now(UTC),
                    status=LogisticsStatus.cancelled,
                )
            await session.commit()

        async with async_session_factory() as session:
            # A cancelled shipment never left -> its quantity is free to re-ship.
            remaining = await get_product_shipped_remaining(session, product.id)
            assert remaining == Decimal("20")
    finally:
        await _cleanup(client.id, supplier.id)


@pytest.mark.asyncio
async def test_validate_exclude_logistics_id_allows_reediting_same_shipment():
    client, supplier, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            logistics = await add_shipment(
                            session,
                            lines=[(product.id, Decimal("20"))],
                            order_id=order.id,
                            created_by_id=admin.id,
                            ship_date=datetime.now(UTC),
                        )
            await session.commit()
            await session.refresh(logistics)

        async with async_session_factory() as session:
            # Re-saving the same shipment with the same quantity should not double-count itself.
            await validate_logistics_items(
                session, [(product.id, Decimal("20"))], exclude_logistics_id=logistics.id
            )
    finally:
        await _cleanup(client.id, supplier.id)
