"""Profit calculation service — ТЗ §11 examples.

Formula: Income − Purchases − Logistics − Other expenses = Profit
All amounts converted to order currency via: value = amount * exchange_rate
(exchange_rate is stored as "order-currency units per 1 operation-currency unit").
"""

from datetime import datetime, timezone
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
from app.services.profit import ProfitBreakdown, calculate_profit

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


async def _cleanup(client_code: str, user_logins: list[str]) -> None:
    async with async_session_factory() as session:
        order_ids = (
            await session.execute(select(Order.id).join(Client).where(Client.code == client_code))
        ).scalars().all()
        if order_ids:
            pr_ids = (
                await session.execute(
                    select(PaymentRequest.id).where(PaymentRequest.order_id.in_(order_ids))
                )
            ).scalars().all()
            if pr_ids:
                await session.execute(delete(Payment).where(Payment.payment_request_id.in_(pr_ids)))
                await session.execute(
                    delete(PaymentRequestItem).where(PaymentRequestItem.payment_request_id.in_(pr_ids))
                )
                await session.execute(delete(PaymentRequest).where(PaymentRequest.order_id.in_(order_ids)))
            await session.execute(delete(LedgerEntry).where(LedgerEntry.order_id.in_(order_ids)))
            await session.execute(delete(Logistics).where(Logistics.order_id.in_(order_ids)))
            prod_ids = (
                await session.execute(select(Product.id).where(Product.order_id.in_(order_ids)))
            ).scalars().all()
            if prod_ids:
                await session.execute(delete(Product).where(Product.id.in_(prod_ids)))
        await session.execute(delete(Order).where(Order.id.in_(order_ids or [])))
        await session.execute(
            delete(Supplier).where(Supplier.name.like("PrftSupplier%"))
        )
        client_ids = (
            await session.execute(select(Client.id).where(Client.code == client_code))
        ).scalars().all()
        await session.execute(delete(Client).where(Client.id.in_(client_ids)))
        await session.execute(delete(User).where(User.login.in_(user_logins)))
        await session.commit()


@pytest.mark.asyncio
async def test_rub_order_tz_example_1():
    """ТЗ §11 Example 1: RUB order with multi-currency operations.

    Income:    200 000 RUB × 1  + 500 USD × 90     = 245 000 RUB
    Purchases: 4 000 CNY × 11   + 7 000 CNY × 11   = 121 000 RUB
    Logistics: 40 000 RUB × 1                       =  40 000 RUB
    Expenses:  10 000 RUB × 1                       =  10 000 RUB
    Profit:    245 000 − 121 000 − 40 000 − 10 000  =  74 000 RUB
    """
    try:
        async with async_session_factory() as session:
            client = Client(code="TSTPRFT1", full_name="Profit Test RUB")
            mgr = User(login="prft1_mgr", password_hash=hash_password("x"), role=UserRole.manager, full_name="PrftMgr1")
            adm = User(login="prft1_adm", password_hash=hash_password("x"), role=UserRole.admin, full_name="PrftAdm1")
            sup = Supplier(name="PrftSupplier1")
            session.add_all([client, mgr, adm, sup])
            await session.commit()
            for o in (client, mgr, adm, sup):
                await session.refresh(o)

            order = Order(number="TSTPRFT1-1", client_id=client.id, manager_id=mgr.id,
                          status=OrderStatus.in_progress, currency="RUB")
            session.add(order)
            await session.commit()
            await session.refresh(order)

            # Two income entries
            session.add_all([
                LedgerEntry(order_id=order.id, author_id=mgr.id, type=LedgerEntryType.income,
                            amount=Decimal("200000.00"), currency="RUB", exchange_rate=Decimal("1.000000")),
                LedgerEntry(order_id=order.id, author_id=mgr.id, type=LedgerEntryType.income,
                            amount=Decimal("500.00"), currency="USD", exchange_rate=Decimal("90.000000")),
            ])

            # Product needed for logistics and payment-request-item
            product = Product(order_id=order.id, supplier_id=sup.id, name="Goods",
                              quantity=Decimal("100.000"), price=Decimal("11.00"), currency="CNY")
            session.add(product)
            await session.commit()
            await session.refresh(product)

            # PaymentRequest + two CNY payments
            pr = PaymentRequest(order_id=order.id, created_by_id=mgr.id)
            session.add(pr)
            await session.commit()
            await session.refresh(pr)

            session.add(PaymentRequestItem(payment_request_id=pr.id, product_id=product.id,
                                           amount=Decimal("1210.00")))
            session.add_all([
                Payment(payment_request_id=pr.id, author_id=mgr.id,
                        amount=Decimal("4000.00"), currency="CNY", exchange_rate=Decimal("11.000000")),
                Payment(payment_request_id=pr.id, author_id=mgr.id,
                        amount=Decimal("7000.00"), currency="CNY", exchange_rate=Decimal("11.000000")),
            ])

            # Accepted logistics with RUB expense
            session.add(Logistics(
                order_id=order.id, product_id=product.id, created_by_id=adm.id,
                quantity=Decimal("50.000"), tracking="PRFT1-TRK", ship_date=_NOW,
                status=LogisticsStatus.accepted,
                expense_amount=Decimal("40000.00"), currency="RUB", exchange_rate=Decimal("1.000000"),
            ))

            # One expense entry
            session.add(LedgerEntry(order_id=order.id, author_id=mgr.id, type=LedgerEntryType.expense,
                                    amount=Decimal("10000.00"), currency="RUB", exchange_rate=Decimal("1.000000")))
            await session.commit()

        async with async_session_factory() as session:
            b = await calculate_profit(order.id, session)

        assert b.currency == "RUB"
        assert b.income == Decimal("245000")
        assert b.purchases == Decimal("121000")
        assert b.logistics == Decimal("40000")
        assert b.other_expenses == Decimal("10000")
        assert b.profit == Decimal("74000")
    finally:
        await _cleanup("TSTPRFT1", ["prft1_mgr", "prft1_adm"])


@pytest.mark.asyncio
async def test_usd_order_tz_example_2():
    """ТЗ §11 Example 2: USD order with multi-currency operations (logic identical to ТЗ §11 example 2).

    Income:    1 000 USD × 1   + 500 CNY × 0.2     = 1 100 USD
    Purchases: 400 CNY × 0.2                        =    80 USD
    Logistics: 300 RUB × 0.01                       =     3 USD
    Expenses:  50 USD × 1                           =    50 USD
    Profit:    1 100 − 80 − 3 − 50                  =   967 USD

    Rates express "USD per 1 unit of operation currency":
    0.2 USD/CNY  → 1 USD = 5 CNY
    0.01 USD/RUB → 1 USD = 100 RUB
    (Uses exact 6-decimal Numeric representations for DB precision.)
    """
    try:
        async with async_session_factory() as session:
            client = Client(code="TSTPRFT2", full_name="Profit Test USD")
            mgr = User(login="prft2_mgr", password_hash=hash_password("x"), role=UserRole.manager, full_name="PrftMgr2")
            adm = User(login="prft2_adm", password_hash=hash_password("x"), role=UserRole.admin, full_name="PrftAdm2")
            sup = Supplier(name="PrftSupplier2")
            session.add_all([client, mgr, adm, sup])
            await session.commit()
            for o in (client, mgr, adm, sup):
                await session.refresh(o)

            order = Order(number="TSTPRFT2-1", client_id=client.id, manager_id=mgr.id,
                          status=OrderStatus.in_progress, currency="USD")
            session.add(order)
            await session.commit()
            await session.refresh(order)

            # Income: 1000 USD × 1 + 500 CNY × 0.2 = 1100 USD
            session.add_all([
                LedgerEntry(order_id=order.id, author_id=mgr.id, type=LedgerEntryType.income,
                            amount=Decimal("1000.00"), currency="USD", exchange_rate=Decimal("1.000000")),
                LedgerEntry(order_id=order.id, author_id=mgr.id, type=LedgerEntryType.income,
                            amount=Decimal("500.00"), currency="CNY", exchange_rate=Decimal("0.200000")),
            ])

            product = Product(order_id=order.id, supplier_id=sup.id, name="Goods USD",
                              quantity=Decimal("100.000"), price=Decimal("1.00"), currency="USD")
            session.add(product)
            await session.commit()
            await session.refresh(product)

            # Purchase: 400 CNY × 0.2 = 80 USD
            pr = PaymentRequest(order_id=order.id, created_by_id=mgr.id)
            session.add(pr)
            await session.commit()
            await session.refresh(pr)

            session.add(PaymentRequestItem(payment_request_id=pr.id, product_id=product.id,
                                           amount=Decimal("80.00")))
            session.add(Payment(payment_request_id=pr.id, author_id=mgr.id,
                                amount=Decimal("400.00"), currency="CNY", exchange_rate=Decimal("0.200000")))

            # Accepted logistics: 300 RUB × 0.01 = 3 USD
            session.add(Logistics(
                order_id=order.id, product_id=product.id, created_by_id=adm.id,
                quantity=Decimal("50.000"), tracking="PRFT2-TRK", ship_date=_NOW,
                status=LogisticsStatus.accepted,
                expense_amount=Decimal("300.00"), currency="RUB", exchange_rate=Decimal("0.010000"),
            ))

            # Other expense: 50 USD × 1 = 50 USD
            session.add(LedgerEntry(order_id=order.id, author_id=mgr.id, type=LedgerEntryType.expense,
                                    amount=Decimal("50.00"), currency="USD", exchange_rate=Decimal("1.000000")))
            await session.commit()

        async with async_session_factory() as session:
            b = await calculate_profit(order.id, session)

        assert b.currency == "USD"
        assert b.income == Decimal("1100")
        assert b.purchases == Decimal("80")
        assert b.logistics == Decimal("3")
        assert b.other_expenses == Decimal("50")
        assert b.profit == Decimal("967")
    finally:
        await _cleanup("TSTPRFT2", ["prft2_mgr", "prft2_adm"])


@pytest.mark.asyncio
async def test_empty_order_has_zero_profit():
    """Order with no operations: all components are zero, profit is zero."""
    try:
        async with async_session_factory() as session:
            client = Client(code="TSTPRFT0", full_name="Profit Empty")
            mgr = User(login="prft0_mgr", password_hash=hash_password("x"), role=UserRole.manager, full_name="PrftMgr0")
            session.add_all([client, mgr])
            await session.commit()
            for o in (client, mgr):
                await session.refresh(o)

            order = Order(number="TSTPRFT0-1", client_id=client.id, manager_id=mgr.id,
                          status=OrderStatus.in_progress, currency="RUB")
            session.add(order)
            await session.commit()
            await session.refresh(order)

        async with async_session_factory() as session:
            b = await calculate_profit(order.id, session)

        assert b.profit == Decimal("0")
        assert b.income == Decimal("0")
        assert b.purchases == Decimal("0")
        assert b.logistics == Decimal("0")
        assert b.other_expenses == Decimal("0")
    finally:
        await _cleanup("TSTPRFT0", ["prft0_mgr"])


@pytest.mark.asyncio
async def test_in_transit_logistics_not_counted():
    """Logistics in 'in_transit' status must NOT count toward logistics cost."""
    try:
        async with async_session_factory() as session:
            client = Client(code="TSTPRFT3", full_name="Profit Transit")
            mgr = User(login="prft3_mgr", password_hash=hash_password("x"), role=UserRole.manager, full_name="PrftMgr3")
            sup = Supplier(name="PrftSupplier3")
            session.add_all([client, mgr, sup])
            await session.commit()
            for o in (client, mgr, sup):
                await session.refresh(o)

            order = Order(number="TSTPRFT3-1", client_id=client.id, manager_id=mgr.id,
                          status=OrderStatus.in_progress, currency="USD")
            session.add(order)
            await session.commit()
            await session.refresh(order)

            product = Product(order_id=order.id, supplier_id=sup.id, name="Goods3",
                              quantity=Decimal("10.000"), price=Decimal("10.00"), currency="USD")
            session.add(product)
            await session.commit()
            await session.refresh(product)

            # in_transit logistics with expense set (should be ignored)
            session.add(Logistics(
                order_id=order.id, product_id=product.id, created_by_id=mgr.id,
                quantity=Decimal("10.000"), tracking="PRFT3-TRK", ship_date=_NOW,
                status=LogisticsStatus.in_transit,
                expense_amount=Decimal("999.00"), currency="USD", exchange_rate=Decimal("1.000000"),
            ))
            await session.commit()

        async with async_session_factory() as session:
            b = await calculate_profit(order.id, session)

        assert b.logistics == Decimal("0")
        assert b.profit == Decimal("0")
    finally:
        await _cleanup("TSTPRFT3", ["prft3_mgr"])
