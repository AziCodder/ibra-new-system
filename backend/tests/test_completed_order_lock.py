"""G3: a completed order's children (products, logistics, payment requests,
payments, ledger entries) must be frozen for every role, including admin —
notes are the deliberate exception (see notes.py)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.action_log import ActionLog
from app.models.client import Client
from app.models.ledger_entry import LedgerEntry
from app.models.logistics import Logistics, LogisticsStatus
from app.models.order import Order, OrderStatus
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest, PaymentRequestItem
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.routers.ledger_entries import create_ledger_entry
from app.routers.logistics import create_logistics, unaccept_logistics
from app.routers.notes import create_note
from app.routers.orders import OrderStatusIn, set_order_status
from app.routers.payment_requests import create_payment_request
from app.routers.payments import create_payment
from app.routers.products import create_product
from app.schemas.ledger_entry import LedgerEntryCreate
from app.schemas.logistics import LogisticsAccept, LogisticsCreate
from app.schemas.note import NoteCreate
from app.schemas.payment import PaymentCreate
from app.schemas.payment_request import PaymentRequestCreate, PaymentRequestItemIn
from app.schemas.product import ProductCreate

SHIP_DATE = datetime.now(UTC)


async def _setup_completed_order():
    async with async_session_factory() as session:
        client = Client(code="TSTCOMP", full_name="Completed Lock Client")
        supplier = Supplier(name="Completed Lock Supplier")
        admin = User(login="cl_admin", password_hash=hash_password("x"), role=UserRole.admin, full_name="Admin")
        session.add_all([client, supplier, admin])
        await session.commit()
        for obj in (client, supplier, admin):
            await session.refresh(obj)

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
            order_id=order.id, supplier_id=supplier.id, name="Widget",
            quantity=Decimal("10.000"), price=Decimal("20.00"), currency="USD",
        )
        session.add(product)
        await session.commit()
        await session.refresh(product)

        # Make the order "ready" so it can actually be completed.
        session.add(Logistics(
            order_id=order.id, product_id=product.id, created_by_id=admin.id,
            quantity=Decimal("10.000"), tracking="COMP-TRK", ship_date=SHIP_DATE,
            status=LogisticsStatus.accepted, currency="USD", exchange_rate=Decimal("1.000000"),
        ))
        pr = PaymentRequest(order_id=order.id, created_by_id=admin.id)
        session.add(pr)
        await session.commit()
        await session.refresh(pr)
        session.add(PaymentRequestItem(payment_request_id=pr.id, product_id=product.id, amount=Decimal("200.00")))
        session.add(Payment(payment_request_id=pr.id, author_id=admin.id, amount=Decimal("200.00"), currency="USD", exchange_rate=Decimal("1.000000")))
        await session.commit()

    async with async_session_factory() as session:
        await set_order_status(order.id, OrderStatusIn(status=OrderStatus.completed), admin, session)

    return client, supplier, admin, order, product, pr


async def _cleanup(client_id: int, supplier_id: int, user_ids: list[int]):
    async with async_session_factory() as session:
        order_ids = select(Order.id).where(Order.client_id == client_id)
        request_ids = select(PaymentRequest.id).where(PaymentRequest.order_id.in_(order_ids))
        await session.execute(delete(Payment).where(Payment.payment_request_id.in_(request_ids)))
        await session.execute(delete(PaymentRequestItem).where(PaymentRequestItem.payment_request_id.in_(request_ids)))
        await session.execute(delete(PaymentRequest).where(PaymentRequest.order_id.in_(order_ids)))
        await session.execute(delete(LedgerEntry).where(LedgerEntry.order_id.in_(order_ids)))
        await session.execute(delete(Logistics).where(Logistics.order_id.in_(order_ids)))
        from app.models.note import Note

        await session.execute(delete(Note).where(Note.order_id.in_(order_ids)))
        await session.execute(delete(Product).where(Product.order_id.in_(order_ids)))
        await session.execute(delete(Order).where(Order.client_id == client_id))
        await session.execute(delete(Client).where(Client.id == client_id))
        await session.execute(delete(Supplier).where(Supplier.id == supplier_id))
        await session.execute(delete(ActionLog).where(ActionLog.actor_id.in_(user_ids)))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_admin_cannot_add_product_to_completed_order():
    client, supplier, admin, order, product, pr = await _setup_completed_order()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_product(
                    order.id,
                    ProductCreate(supplier_id=supplier.id, name="New Widget", quantity=Decimal("1"), price=Decimal("1")),
                    admin,
                    session,
                )
            assert exc_info.value.status_code == 409
    finally:
        await _cleanup(client.id, supplier.id, [admin.id])


@pytest.mark.asyncio
async def test_admin_cannot_create_logistics_on_completed_order():
    client, supplier, admin, order, product, pr = await _setup_completed_order()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_logistics(
                    order.id,
                    LogisticsCreate(product_id=product.id, quantity=Decimal("1"), ship_date=SHIP_DATE),
                    admin,
                    session,
                )
            assert exc_info.value.status_code == 409
    finally:
        await _cleanup(client.id, supplier.id, [admin.id])


@pytest.mark.asyncio
async def test_admin_cannot_unaccept_logistics_on_completed_order():
    # Closes the QA-report gap: unaccept had no protection against a completed order.
    client, supplier, admin, order, product, pr = await _setup_completed_order()
    try:
        async with async_session_factory() as session:
            logistics = (
                await session.execute(select(Logistics).where(Logistics.order_id == order.id))
            ).scalar_one()

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await unaccept_logistics(order.id, logistics.id, admin, session)
            assert exc_info.value.status_code == 409
    finally:
        await _cleanup(client.id, supplier.id, [admin.id])


@pytest.mark.asyncio
async def test_admin_cannot_create_payment_request_on_completed_order():
    client, supplier, admin, order, product, pr = await _setup_completed_order()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_payment_request(
                    order.id,
                    PaymentRequestCreate(items=[PaymentRequestItemIn(product_id=product.id, amount=Decimal("1.00"))]),
                    admin,
                    session,
                )
            assert exc_info.value.status_code == 409
    finally:
        await _cleanup(client.id, supplier.id, [admin.id])


@pytest.mark.asyncio
async def test_admin_cannot_create_payment_on_completed_order():
    client, supplier, admin, order, product, pr = await _setup_completed_order()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_payment(
                    order.id, pr.id,
                    PaymentCreate(amount=Decimal("1.00"), currency="USD", exchange_rate=Decimal("1")),
                    admin, session,
                )
            assert exc_info.value.status_code == 409
    finally:
        await _cleanup(client.id, supplier.id, [admin.id])


@pytest.mark.asyncio
async def test_admin_cannot_create_ledger_entry_on_completed_order():
    client, supplier, admin, order, product, pr = await _setup_completed_order()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_ledger_entry(
                    order.id,
                    LedgerEntryCreate(type="expense", amount=Decimal("1.00"), currency="USD", exchange_rate=Decimal("1")),
                    admin,
                    session,
                )
            assert exc_info.value.status_code == 409
    finally:
        await _cleanup(client.id, supplier.id, [admin.id])


@pytest.mark.asyncio
async def test_notes_still_allowed_on_completed_order():
    # Deliberate exception — notes don't feed the frozen profit snapshot.
    client, supplier, admin, order, product, pr = await _setup_completed_order()
    try:
        async with async_session_factory() as session:
            created = await create_note(order.id, NoteCreate(text="post-completion note"), admin, session)
            assert created.text == "post-completion note"
    finally:
        await _cleanup(client.id, supplier.id, [admin.id])


@pytest.mark.asyncio
async def test_reverting_to_in_progress_unlocks_editing():
    client, supplier, admin, order, product, pr = await _setup_completed_order()
    try:
        async with async_session_factory() as session:
            await set_order_status(order.id, OrderStatusIn(status=OrderStatus.in_progress), admin, session)

        async with async_session_factory() as session:
            created = await create_product(
                order.id,
                ProductCreate(supplier_id=supplier.id, name="New Widget", quantity=Decimal("1"), price=Decimal("1")),
                admin,
                session,
            )
            assert created.name == "New Widget"
    finally:
        await _cleanup(client.id, supplier.id, [admin.id])
