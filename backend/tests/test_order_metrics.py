"""Tests for snapshot_order_metrics (task 9.3)."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.client import Client
from app.models.ledger_entry import LedgerEntry, LedgerEntryType
from app.models.logistics import Logistics, LogisticsStatus
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.services.order_metrics import snapshot_order_metrics


async def _cleanup(client_code: str, logins: list[str]) -> None:
    async with async_session_factory() as session:
        order_ids = (
            await session.execute(select(Order.id).join(Client).where(Client.code == client_code))
        ).scalars().all()
        if order_ids:
            await session.execute(delete(LedgerEntry).where(LedgerEntry.order_id.in_(order_ids)))
            await session.execute(delete(Logistics).where(Logistics.order_id.in_(order_ids)))
            await session.execute(delete(Product).where(Product.order_id.in_(order_ids)))
        await session.execute(delete(Order).where(Order.id.in_(order_ids or [])))
        await session.execute(delete(Supplier).where(Supplier.name.like("MtxSupplier%")))
        client_ids = (
            await session.execute(select(Client.id).where(Client.code == client_code))
        ).scalars().all()
        await session.execute(delete(Client).where(Client.id.in_(client_ids)))
        await session.execute(delete(User).where(User.login.in_(logins)))
        await session.commit()


@pytest.mark.asyncio
async def test_snapshot_not_ready_returns_false():
    """Snapshot returns False and leaves fields NULL when order is not ready (no products)."""
    try:
        async with async_session_factory() as session:
            client = Client(code="TSTMTX0", full_name="Metrics Not Ready")
            mgr = User(login="mtx0_mgr", password_hash=hash_password("x"),
                       role=UserRole.manager, full_name="MtxMgr0")
            session.add_all([client, mgr])
            await session.commit()
            await session.refresh(client)
            await session.refresh(mgr)

            order = Order(number="TSTMTX0-1", client_id=client.id, manager_id=mgr.id,
                          status=OrderStatus.in_progress, currency="RUB")
            session.add(order)
            await session.commit()
            await session.refresh(order)

        async with async_session_factory() as session:
            result = await snapshot_order_metrics(order.id, session)
            await session.commit()

        assert result is False

        async with async_session_factory() as session:
            o = (await session.execute(select(Order).where(Order.id == order.id))).scalar_one()
        assert o.profit_pct is None
        assert o.processing_days is None
    finally:
        await _cleanup("TSTMTX0", ["mtx0_mgr"])


@pytest.mark.asyncio
async def test_snapshot_ready_writes_metrics():
    """When order is ready, profit_pct and processing_days are persisted correctly.

    Setup: 1 product (qty=20), 1 accepted logistics (qty=20) → is_ready=True.
    Income: 1000 RUB → profit=1000 RUB → profit_pct=100%.
    processing_days: order was created today → 0 days.
    """
    try:
        async with async_session_factory() as session:
            client = Client(code="TSTMTX1", full_name="Metrics Ready")
            mgr = User(login="mtx1_mgr", password_hash=hash_password("x"),
                       role=UserRole.manager, full_name="MtxMgr1")
            adm = User(login="mtx1_adm", password_hash=hash_password("x"),
                       role=UserRole.admin, full_name="MtxAdm1")
            sup = Supplier(name="MtxSupplier1")
            session.add_all([client, mgr, adm, sup])
            await session.commit()
            for o in (client, mgr, adm, sup):
                await session.refresh(o)

            order = Order(number="TSTMTX1-1", client_id=client.id, manager_id=mgr.id,
                          status=OrderStatus.in_progress, currency="RUB")
            session.add(order)
            await session.commit()
            await session.refresh(order)

            product = Product(order_id=order.id, supplier_id=sup.id, name="G",
                              quantity=Decimal("20.000"), price=Decimal("10.00"), currency="RUB")
            session.add(product)
            await session.commit()
            await session.refresh(product)

            # Fully accepted shipment covering qty exactly
            session.add(Logistics(
                order_id=order.id, product_id=product.id, created_by_id=adm.id,
                quantity=Decimal("20.000"), tracking="MTX1-TRK",
                ship_date=order.created_at,
                status=LogisticsStatus.accepted,
                expense_amount=None, currency="RUB", exchange_rate=Decimal("1.000000"),
            ))
            # Income: 1000 RUB (no purchases/expenses/logistics cost → profit = 1000)
            session.add(LedgerEntry(
                order_id=order.id, author_id=mgr.id, type=LedgerEntryType.income,
                amount=Decimal("1000.00"), currency="RUB", exchange_rate=Decimal("1.000000"),
                details="",
            ))
            await session.commit()

        async with async_session_factory() as session:
            result = await snapshot_order_metrics(order.id, session)
            await session.commit()

        assert result is True

        async with async_session_factory() as session:
            o = (await session.execute(select(Order).where(Order.id == order.id))).scalar_one()

        assert o.profit_pct is not None
        assert o.profit_pct == Decimal("100.0000")
        assert o.processing_days is not None
        assert o.processing_days == (date.today() - order.created_at.date()).days
    finally:
        await _cleanup("TSTMTX1", ["mtx1_mgr", "mtx1_adm"])


@pytest.mark.asyncio
async def test_snapshot_zero_income_gives_zero_pct():
    """When income=0 and order is ready, profit_pct is stored as 0 (no division by zero)."""
    try:
        async with async_session_factory() as session:
            client = Client(code="TSTMTX2", full_name="Metrics Zero Income")
            mgr = User(login="mtx2_mgr", password_hash=hash_password("x"),
                       role=UserRole.manager, full_name="MtxMgr2")
            adm = User(login="mtx2_adm", password_hash=hash_password("x"),
                       role=UserRole.admin, full_name="MtxAdm2")
            sup = Supplier(name="MtxSupplier2")
            session.add_all([client, mgr, adm, sup])
            await session.commit()
            for o in (client, mgr, adm, sup):
                await session.refresh(o)

            order = Order(number="TSTMTX2-1", client_id=client.id, manager_id=mgr.id,
                          status=OrderStatus.in_progress, currency="RUB")
            session.add(order)
            await session.commit()
            await session.refresh(order)

            product = Product(order_id=order.id, supplier_id=sup.id, name="G",
                              quantity=Decimal("10.000"), price=Decimal("1.00"), currency="RUB")
            session.add(product)
            await session.commit()
            await session.refresh(product)

            # All 10 accepted — ready, but no income entries
            session.add(Logistics(
                order_id=order.id, product_id=product.id, created_by_id=adm.id,
                quantity=Decimal("10.000"), tracking="MTX2-TRK",
                ship_date=order.created_at,
                status=LogisticsStatus.accepted,
                expense_amount=None, currency="RUB", exchange_rate=Decimal("1.000000"),
            ))
            await session.commit()

        async with async_session_factory() as session:
            result = await snapshot_order_metrics(order.id, session)
            await session.commit()

        assert result is True

        async with async_session_factory() as session:
            o = (await session.execute(select(Order).where(Order.id == order.id))).scalar_one()

        assert o.profit_pct == Decimal("0")
    finally:
        await _cleanup("TSTMTX2", ["mtx2_mgr", "mtx2_adm"])
