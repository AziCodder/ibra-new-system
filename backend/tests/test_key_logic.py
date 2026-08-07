"""Consolidated regression tests for Phase 15.1 key business logic.

Covers: access control, profit calculation, balance guards, auto-numbering.
"""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.client import Client
from app.models.ledger_entry import LedgerEntry, LedgerEntryType
from app.models.logistics import Logistics, LogisticsStatus
from app.models.order import Order, OrderStatus
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest, PaymentRequestItem
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.routers.orders import list_orders
from app.services.logistics_validation import LogisticsValidationError, validate_logistics_items
from app.services.order_number import generate_order_number
from app.services.payment_request_validation import (
    PaymentRequestValidationError,
    validate_payment_request_items,
)
from app.services.profit import calculate_profit
from tests.helpers import add_shipment

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


async def _create_order_with_number(client_id: int, manager_id: int) -> str:
    async with async_session_factory() as session:
        async with session.begin():
            number = await generate_order_number(session, client_id)
            session.add(
                Order(
                    number=number,
                    client_id=client_id,
                    manager_id=manager_id,
                    status=OrderStatus.in_progress,
                    currency="USD",
                )
            )
        return number


@pytest.mark.asyncio
@pytest.mark.key_access
async def test_manager_sees_only_own_orders_in_list():
    """Managers must not see other managers' orders in list_orders."""
    async with async_session_factory() as session:
        client = Client(code="KEYACC", full_name="Key Access Client")
        owner = User(login="key_owner", password_hash=hash_password("x"), role=UserRole.manager, full_name="Owner")
        other = User(login="key_other", password_hash=hash_password("x"), role=UserRole.manager, full_name="Other")
        session.add_all([client, owner, other])
        await session.commit()
        for row in (client, owner, other):
            await session.refresh(row)

        session.add_all([
            Order(number="KEYACC-1", client_id=client.id, manager_id=owner.id, status=OrderStatus.in_progress, currency="USD"),
            Order(number="KEYACC-2", client_id=client.id, manager_id=other.id, status=OrderStatus.in_progress, currency="USD"),
        ])
        await session.commit()

    try:
        async with async_session_factory() as session:
            result = await list_orders(session=session, user=owner, page=1, page_size=20)
        assert result.total == 1
        assert result.items[0].number == "KEYACC-1"
        assert all(item.manager_id == owner.id for item in result.items)
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(Order).where(Order.client_id == client.id))
            await session.execute(delete(Client).where(Client.id == client.id))
            await session.execute(delete(User).where(User.login.in_(["key_owner", "key_other"])))
            await session.commit()


@pytest.mark.asyncio
@pytest.mark.key_profit
async def test_profit_calculation_tz_example():
    """ТЗ §11 example 1: income − purchases − logistics − expenses = profit (74k RUB)."""
    async with async_session_factory() as session:
        client = Client(code="KEYPRF", full_name="Key Profit Client")
        mgr = User(login="key_prf_mgr", password_hash=hash_password("x"), role=UserRole.manager, full_name="Mgr")
        adm = User(login="key_prf_adm", password_hash=hash_password("x"), role=UserRole.admin, full_name="Adm")
        sup = Supplier(name="KeyProfitSup")
        session.add_all([client, mgr, adm, sup])
        await session.commit()
        for row in (client, mgr, adm, sup):
            await session.refresh(row)

        order = Order(number="KEYPRF-1", client_id=client.id, manager_id=mgr.id, status=OrderStatus.in_progress, currency="RUB")
        session.add(order)
        await session.commit()
        await session.refresh(order)

        session.add_all([
            LedgerEntry(order_id=order.id, author_id=mgr.id, type=LedgerEntryType.income,
                        amount=Decimal("200000.00"), currency="RUB", exchange_rate=Decimal("1.000000")),
            LedgerEntry(order_id=order.id, author_id=mgr.id, type=LedgerEntryType.income,
                        amount=Decimal("500.00"), currency="USD", exchange_rate=Decimal("90.000000")),
        ])
        product = Product(order_id=order.id, supplier_id=sup.id, name="Goods",
                          quantity=Decimal("100.000"), price=Decimal("11.00"), currency="CNY")
        session.add(product)
        await session.commit()
        await session.refresh(product)

        pr = PaymentRequest(order_id=order.id, created_by_id=mgr.id)
        session.add(pr)
        await session.commit()
        await session.refresh(pr)

        session.add(PaymentRequestItem(payment_request_id=pr.id, product_id=product.id, amount=Decimal("1210.00")))
        session.add_all([
            Payment(payment_request_id=pr.id, author_id=mgr.id,
                    amount=Decimal("4000.00"), currency="CNY", exchange_rate=Decimal("11.000000")),
            Payment(payment_request_id=pr.id, author_id=mgr.id,
                    amount=Decimal("7000.00"), currency="CNY", exchange_rate=Decimal("11.000000")),
        ])
        await add_shipment(
                        session,
                        lines=[(product.id, Decimal("50.000"))],
                        order_id=order.id,
                        created_by_id=adm.id,
                        tracking="KEYPRF-TRK",
                        ship_date=_NOW,
                        status=LogisticsStatus.accepted,
                        expense_amount=Decimal("40000.00"),
                        currency="RUB",
                        exchange_rate=Decimal("1.000000"),
                    )
        session.add(LedgerEntry(order_id=order.id, author_id=mgr.id, type=LedgerEntryType.expense,
                                amount=Decimal("10000.00"), currency="RUB", exchange_rate=Decimal("1.000000")))
        await session.commit()

    try:
        async with async_session_factory() as session:
            breakdown = await calculate_profit(order.id, session)

        assert breakdown.currency == "RUB"
        assert breakdown.income == Decimal("245000")
        assert breakdown.purchases == Decimal("121000")
        assert breakdown.logistics == Decimal("40000")
        assert breakdown.other_expenses == Decimal("10000")
        assert breakdown.profit == Decimal("74000")
    finally:
        async with async_session_factory() as session:
            order_ids = [order.id]
            pr_ids = (await session.execute(select(PaymentRequest.id).where(PaymentRequest.order_id.in_(order_ids)))).scalars().all()
            if pr_ids:
                await session.execute(delete(Payment).where(Payment.payment_request_id.in_(pr_ids)))
                await session.execute(delete(PaymentRequestItem).where(PaymentRequestItem.payment_request_id.in_(pr_ids)))
                await session.execute(delete(PaymentRequest).where(PaymentRequest.id.in_(pr_ids)))
            await session.execute(delete(LedgerEntry).where(LedgerEntry.order_id.in_(order_ids)))
            await session.execute(delete(Logistics).where(Logistics.order_id.in_(order_ids)))
            await session.execute(delete(Product).where(Product.order_id.in_(order_ids)))
            await session.execute(delete(Order).where(Order.id.in_(order_ids)))
            await session.execute(delete(Supplier).where(Supplier.name == "KeyProfitSup"))
            await session.execute(delete(Client).where(Client.id == client.id))
            await session.execute(delete(User).where(User.login.in_(["key_prf_mgr", "key_prf_adm"])))
            await session.commit()


@pytest.mark.asyncio
@pytest.mark.key_balance
async def test_payment_and_shipment_remaining_guards():
    """Cannot overpay a product or over-ship beyond purchased quantity."""
    async with async_session_factory() as session:
        client = Client(code="KEYBAL", full_name="Key Balance Client")
        mgr = User(login="key_bal_mgr", password_hash=hash_password("x"), role=UserRole.manager, full_name="Mgr")
        sup = Supplier(name="KeyBalSup")
        session.add_all([client, mgr, sup])
        await session.commit()
        for row in (client, mgr, sup):
            await session.refresh(row)

        order = Order(number="KEYBAL-1", client_id=client.id, manager_id=mgr.id, status=OrderStatus.in_progress, currency="USD")
        session.add(order)
        await session.commit()
        await session.refresh(order)

        product = Product(order_id=order.id, supplier_id=sup.id, name="W", quantity=Decimal("20"), price=Decimal("10"), currency="USD")
        session.add(product)
        await session.commit()
        await session.refresh(product)

    try:
        async with async_session_factory() as session:
            with pytest.raises(PaymentRequestValidationError):
                await validate_payment_request_items(session, [(product.id, Decimal("201.00"))])

            with pytest.raises(LogisticsValidationError):
                await validate_logistics_items(session, [(product.id, Decimal("21"))])
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(Product).where(Product.id == product.id))
            await session.execute(delete(Order).where(Order.id == order.id))
            await session.execute(delete(Supplier).where(Supplier.id == sup.id))
            await session.execute(delete(Client).where(Client.id == client.id))
            await session.execute(delete(User).where(User.login == "key_bal_mgr"))
            await session.commit()


@pytest.mark.asyncio
@pytest.mark.key_numbering
async def test_order_auto_numbering_under_concurrency():
    """Two concurrent creates for the same client get sequential unique numbers."""
    async with async_session_factory() as session:
        client = Client(code="KEYNUM", full_name="Key Number Client")
        session.add(client)
        await session.commit()
        await session.refresh(client)
        manager = (await session.execute(select(User).where(User.role == UserRole.admin).limit(1))).scalar_one()

    try:
        numbers = await asyncio.gather(
            _create_order_with_number(client.id, manager.id),
            _create_order_with_number(client.id, manager.id),
        )
        assert sorted(numbers) == ["KEYNUM-1", "KEYNUM-2"]
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(Order).where(Order.client_id == client.id))
            await session.execute(delete(Client).where(Client.id == client.id))
            await session.commit()
