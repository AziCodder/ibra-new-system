"""Tests for order status transitions (ТЗ §13)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.action_log import ActionLog
from app.models.client import Client
from app.models.logistics import Logistics, LogisticsStatus
from app.models.order import Order, OrderStatus
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest, PaymentRequestItem
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.routers.orders import OrderStatusIn, set_order_status
from app.services.order_metrics import snapshot_order_metrics
from tests.helpers import add_shipment

# ── Fixtures ──────────────────────────────────────────────────────────────────

async def _setup():
    async with async_session_factory() as session:
        client = Client(code="TSTOST", full_name="Status Test Client")
        supplier = Supplier(name="StatusSupplier")
        owner = User(login="ost_owner", password_hash=hash_password("x"),
                     role=UserRole.manager, full_name="Owner Mgr")
        other = User(login="ost_other", password_hash=hash_password("x"),
                     role=UserRole.manager, full_name="Other Mgr")
        observer = User(login="ost_obs", password_hash=hash_password("x"),
                        role=UserRole.observer, full_name="Observer")
        admin = User(login="ost_admin", password_hash=hash_password("x"),
                     role=UserRole.admin, full_name="Admin")
        session.add_all([client, supplier, owner, other, observer, admin])
        await session.commit()
        for o in (client, supplier, owner, other, observer, admin):
            await session.refresh(o)

        order = Order(number="TSTOST-1", client_id=client.id, manager_id=owner.id,
                      status=OrderStatus.in_progress, currency="USD")
        session.add(order)
        await session.commit()
        await session.refresh(order)

        product = Product(order_id=order.id, supplier_id=supplier.id, name="Widget",
                          quantity=Decimal("10.000"), price=Decimal("20.00"), currency="USD")
        session.add(product)
        await session.commit()
        await session.refresh(product)

        return client, supplier, owner, other, observer, admin, order, product


async def _setup_ready_order(client, supplier, owner, admin, order, product):
    """Add accepted logistics covering full qty + fully paid payment request."""
    async with async_session_factory() as session:
        await add_shipment(
                        session,
                        lines=[(product.id, Decimal("10.000"))],
                        order_id=order.id,
                        created_by_id=admin.id,
                        tracking="OST-TRK",
                        ship_date=order.created_at,
                        status=LogisticsStatus.accepted,
                        expense_amount=None,
                        currency="USD",
                        exchange_rate=Decimal("1.000000"),
                    )
        pr = PaymentRequest(order_id=order.id, created_by_id=owner.id)
        session.add(pr)
        await session.commit()
        await session.refresh(pr)

        session.add(PaymentRequestItem(payment_request_id=pr.id, product_id=product.id,
                                       amount=Decimal("200.00")))
        session.add(Payment(payment_request_id=pr.id, author_id=admin.id,
                            amount=Decimal("200.00"), currency="USD", exchange_rate=Decimal("1.000000")))
        await session.commit()
        return pr


async def _cleanup(client_id: int, supplier_id: int, user_ids: list[int]):
    async with async_session_factory() as session:
        order_ids_sq = select(Order.id).where(Order.client_id == client_id)
        pr_ids_sq = select(PaymentRequest.id).where(PaymentRequest.order_id.in_(order_ids_sq))
        await session.execute(delete(Payment).where(Payment.payment_request_id.in_(pr_ids_sq)))
        await session.execute(delete(PaymentRequestItem).where(PaymentRequestItem.payment_request_id.in_(pr_ids_sq)))
        await session.execute(delete(PaymentRequest).where(PaymentRequest.order_id.in_(order_ids_sq)))
        await session.execute(delete(Logistics).where(Logistics.order_id.in_(order_ids_sq)))
        await session.execute(delete(Product).where(Product.order_id.in_(order_ids_sq)))
        await session.execute(delete(Order).where(Order.client_id == client_id))
        await session.execute(delete(Client).where(Client.id == client_id))
        await session.execute(delete(Supplier).where(Supplier.id == supplier_id))
        # Audit rows (Phase 12.2) reference users via FK — remove before users.
        await session.execute(delete(ActionLog).where(ActionLog.actor_id.in_(user_ids)))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_manager_can_cancel_own_order():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            out = await set_order_status(order.id, OrderStatusIn(status=OrderStatus.cancelled), owner, session)
        assert out.status == OrderStatus.cancelled
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_manager_cannot_cancel_other_managers_order():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await set_order_status(order.id, OrderStatusIn(status=OrderStatus.cancelled), other, session)
        assert exc_info.value.status_code == 404
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_observer_cannot_change_status():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await set_order_status(order.id, OrderStatusIn(status=OrderStatus.cancelled), observer, session)
        assert exc_info.value.status_code == 403
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_admin_cannot_complete_when_not_ready():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await set_order_status(order.id, OrderStatusIn(status=OrderStatus.completed), admin, session)
        assert exc_info.value.status_code == 409
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_admin_can_complete_when_ready():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        await _setup_ready_order(client, supplier, owner, admin, order, product)
        async with async_session_factory() as session:
            out = await set_order_status(order.id, OrderStatusIn(status=OrderStatus.completed), admin, session)
        assert out.status == OrderStatus.completed
        assert out.completed_at is not None

        async with async_session_factory() as session:
            o = (await session.execute(select(Order).where(Order.id == order.id))).scalar_one()
        assert o.completed_at is not None
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_manager_cannot_complete():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        await _setup_ready_order(client, supplier, owner, admin, order, product)
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await set_order_status(order.id, OrderStatusIn(status=OrderStatus.completed), owner, session)
        assert exc_info.value.status_code == 403
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_admin_can_revert_cancelled_to_in_progress():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            await set_order_status(order.id, OrderStatusIn(status=OrderStatus.cancelled), admin, session)
        async with async_session_factory() as session:
            out = await set_order_status(order.id, OrderStatusIn(status=OrderStatus.in_progress), admin, session)
        assert out.status == OrderStatus.in_progress
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_completed_cannot_become_cancelled():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        await _setup_ready_order(client, supplier, owner, admin, order, product)
        async with async_session_factory() as session:
            await set_order_status(order.id, OrderStatusIn(status=OrderStatus.completed), admin, session)
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await set_order_status(order.id, OrderStatusIn(status=OrderStatus.cancelled), admin, session)
        assert exc_info.value.status_code == 409
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_revert_completed_clears_completed_at():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        await _setup_ready_order(client, supplier, owner, admin, order, product)
        async with async_session_factory() as session:
            await set_order_status(order.id, OrderStatusIn(status=OrderStatus.completed), admin, session)
        async with async_session_factory() as session:
            await set_order_status(order.id, OrderStatusIn(status=OrderStatus.in_progress), admin, session)
        async with async_session_factory() as session:
            o = (await session.execute(select(Order).where(Order.id == order.id))).scalar_one()
        assert o.status == OrderStatus.in_progress
        assert o.completed_at is None
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_processing_days_freezes_at_completed_at_not_today():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        await _setup_ready_order(client, supplier, owner, admin, order, product)

        async with async_session_factory() as session:
            o = (await session.execute(select(Order).where(Order.id == order.id))).scalar_one()
            o.created_at = datetime.now(UTC) - timedelta(days=10)
            o.completed_at = datetime.now(UTC) - timedelta(days=3)
            await session.commit()

        # Recompute the snapshot again (this is what every GET /profit does after
        # completion) — processing_days must stay pinned to completed_at, not grow
        # with today's date.
        async with async_session_factory() as session:
            await snapshot_order_metrics(order.id, session)
            await session.commit()

        async with async_session_factory() as session:
            o = (await session.execute(select(Order).where(Order.id == order.id))).scalar_one()
            assert o.processing_days == 7
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])
