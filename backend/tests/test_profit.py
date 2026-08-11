"""Profit calculation service — ТЗ §11 examples.

Formula: Income − Purchases − Logistics − Other expenses = Profit
All amounts converted to order currency via: value = amount / exchange_rate
(exchange_rate is stored as "operation-currency units per 1 order-currency unit",
i.e. exactly what the forms ask for: "1 CNY = 11.5 RUB" -> 11.5).
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
from tests.helpers import add_shipment

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

    Income:    200 000 RUB / 1  +   450 USD / 0.01  = 245 000 RUB
    Purchases: 4 000 CNY + 8 100 CNY, / 0.1         = 121 000 RUB
    Logistics: 40 000 RUB / 1                       =  40 000 RUB
    Expenses:  10 000 RUB / 1                       =  10 000 RUB
    Profit:    245 000 − 121 000 − 40 000 − 10 000  =  74 000 RUB

    Rates read "operation currency per 1 RUB", so 1 RUB = 0.01 USD (100 RUB per
    dollar) and 1 RUB = 0.1 CNY (10 RUB per yuan). The ТЗ's own quotes (90 RUB/USD,
    11 RUB/CNY) have no exact 6-decimal inverse, so the foreign amounts are picked
    to land on the same totals the ТЗ example asserts.

    The purchase is priced in CNY, so the RUB→CNY rate lives on the product; the
    payments are themselves in CNY, i.e. already in the payment request's currency,
    hence their own rate is 1.
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
                            amount=Decimal("450.00"), currency="USD", exchange_rate=Decimal("0.010000")),
            ])

            # Product needed for logistics and payment-request-item
            product = Product(order_id=order.id, supplier_id=sup.id, name="Goods",
                              quantity=Decimal("100.000"), price=Decimal("121.00"), currency="CNY",
                              exchange_rate=Decimal("0.100000"))
            session.add(product)
            await session.commit()
            await session.refresh(product)

            # PaymentRequest + two CNY payments
            pr = PaymentRequest(order_id=order.id, created_by_id=mgr.id)
            session.add(pr)
            await session.commit()
            await session.refresh(pr)

            session.add(PaymentRequestItem(payment_request_id=pr.id, product_id=product.id,
                                           amount=Decimal("12100.00")))
            session.add_all([
                Payment(payment_request_id=pr.id, author_id=mgr.id,
                        amount=Decimal("4000.00"), currency="CNY", exchange_rate=Decimal("1.000000")),
                Payment(payment_request_id=pr.id, author_id=mgr.id,
                        amount=Decimal("8100.00"), currency="CNY", exchange_rate=Decimal("1.000000")),
            ])

            # Accepted logistics with RUB expense
            await add_shipment(
                            session,
                            lines=[(product.id, Decimal("50.000"))],
                            order_id=order.id,
                            created_by_id=adm.id,
                            tracking="PRFT1-TRK",
                            ship_date=_NOW,
                            status=LogisticsStatus.accepted,
                            expense_amount=Decimal("40000.00"),
                            currency="RUB",
                            exchange_rate=Decimal("1.000000"),
                        )

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

    Income:    1 000 USD / 1   + 500 CNY / 5       = 1 100 USD
    Purchases: 400 CNY / 5                          =    80 USD
    Logistics: 300 RUB / 100                        =     3 USD
    Expenses:  50 USD / 1                           =    50 USD
    Profit:    1 100 − 80 − 3 − 50                  =   967 USD

    Rates express "operation currency per 1 USD":
    1 USD = 5 CNY
    1 USD = 100 RUB
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

            # Income: 1000 USD / 1 + 500 CNY / 5 = 1100 USD
            session.add_all([
                LedgerEntry(order_id=order.id, author_id=mgr.id, type=LedgerEntryType.income,
                            amount=Decimal("1000.00"), currency="USD", exchange_rate=Decimal("1.000000")),
                LedgerEntry(order_id=order.id, author_id=mgr.id, type=LedgerEntryType.income,
                            amount=Decimal("500.00"), currency="CNY", exchange_rate=Decimal("5.000000")),
            ])

            product = Product(order_id=order.id, supplier_id=sup.id, name="Goods USD",
                              quantity=Decimal("100.000"), price=Decimal("1.00"), currency="USD")
            session.add(product)
            await session.commit()
            await session.refresh(product)

            # Purchase: 400 CNY / 5 = 80 USD
            pr = PaymentRequest(order_id=order.id, created_by_id=mgr.id)
            session.add(pr)
            await session.commit()
            await session.refresh(pr)

            session.add(PaymentRequestItem(payment_request_id=pr.id, product_id=product.id,
                                           amount=Decimal("80.00")))
            session.add(Payment(payment_request_id=pr.id, author_id=mgr.id,
                                amount=Decimal("400.00"), currency="CNY", exchange_rate=Decimal("5.000000")))

            # Accepted logistics: 300 RUB / 100 = 3 USD
            await add_shipment(
                            session,
                            lines=[(product.id, Decimal("50.000"))],
                            order_id=order.id,
                            created_by_id=adm.id,
                            tracking="PRFT2-TRK",
                            ship_date=_NOW,
                            status=LogisticsStatus.accepted,
                            expense_amount=Decimal("300.00"),
                            currency="RUB",
                            exchange_rate=Decimal("100.000000"),
                        )

            # Other expense: 50 USD / 1 = 50 USD
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
@pytest.mark.key_profit
async def test_purchases_convert_through_both_the_payment_and_the_product_rate():
    """A payment in a third currency, against a product priced in a second one.

    Order is USD. The product is priced in CNY (1 USD = 8 CNY), so the payment
    request is a CNY request. The payment itself is made in RUB, and its own rate
    converts RUB into that request's currency (1 CNY = 12.5 RUB).

    Purchases: 5 000 RUB / 12.5 = 400 CNY, / 8 = 50 USD

    Neither rate alone gets there — this is what regressed when a product could
    only ever be priced in its order's currency.
    """
    try:
        async with async_session_factory() as session:
            client = Client(code="TSTPRFT4", full_name="Profit Two Hops")
            mgr = User(login="prft4_mgr", password_hash=hash_password("x"), role=UserRole.manager, full_name="PrftMgr4")
            sup = Supplier(name="PrftSupplier4")
            session.add_all([client, mgr, sup])
            await session.commit()
            for o in (client, mgr, sup):
                await session.refresh(o)

            order = Order(number="TSTPRFT4-1", client_id=client.id, manager_id=mgr.id,
                          status=OrderStatus.in_progress, currency="USD")
            session.add(order)
            await session.commit()
            await session.refresh(order)

            product = Product(order_id=order.id, supplier_id=sup.id, name="Imported",
                              quantity=Decimal("10.000"), price=Decimal("100.00"), currency="CNY",
                              exchange_rate=Decimal("8.000000"))
            session.add(product)
            await session.commit()
            await session.refresh(product)

            pr = PaymentRequest(order_id=order.id, created_by_id=mgr.id)
            session.add(pr)
            await session.commit()
            await session.refresh(pr)

            session.add(PaymentRequestItem(payment_request_id=pr.id, product_id=product.id,
                                           amount=Decimal("1000.00")))
            session.add(Payment(payment_request_id=pr.id, author_id=mgr.id,
                                amount=Decimal("5000.00"), currency="RUB", exchange_rate=Decimal("12.500000")))
            await session.commit()

        async with async_session_factory() as session:
            b = await calculate_profit(order.id, session)

        assert b.currency == "USD"
        assert b.purchases == Decimal("50.0000")
        assert b.profit == Decimal("-50.0000")
    finally:
        await _cleanup("TSTPRFT4", ["prft4_mgr"])


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
            await add_shipment(
                            session,
                            lines=[(product.id, Decimal("10.000"))],
                            order_id=order.id,
                            created_by_id=mgr.id,
                            tracking="PRFT3-TRK",
                            ship_date=_NOW,
                            status=LogisticsStatus.in_transit,
                            expense_amount=Decimal("999.00"),
                            currency="USD",
                            exchange_rate=Decimal("1.000000"),
                        )
            await session.commit()

        async with async_session_factory() as session:
            b = await calculate_profit(order.id, session)

        assert b.logistics == Decimal("0")
        assert b.profit == Decimal("0")
        assert b.is_ready is False  # in_transit logistics → not ready
    finally:
        await _cleanup("TSTPRFT3", ["prft3_mgr"])


# ── Readiness-condition tests (ТЗ §11 §9.2) ──────────────────────────────────

@pytest.mark.asyncio
async def test_readiness_false_no_products():
    """Order with no products is not ready (nothing shipped)."""
    try:
        async with async_session_factory() as session:
            client = Client(code="TSTPRFTR0", full_name="Ready Empty")
            mgr = User(login="prftr0_mgr", password_hash=hash_password("x"), role=UserRole.manager, full_name="RMgr0")
            session.add_all([client, mgr])
            await session.commit()
            for o in (client, mgr):
                await session.refresh(o)
            order = Order(number="TSTPRFTR0-1", client_id=client.id, manager_id=mgr.id,
                          status=OrderStatus.in_progress, currency="RUB")
            session.add(order)
            await session.commit()
            await session.refresh(order)

        async with async_session_factory() as session:
            b = await calculate_profit(order.id, session)

        assert b.is_ready is False
    finally:
        await _cleanup("TSTPRFTR0", ["prftr0_mgr"])


@pytest.mark.asyncio
async def test_readiness_false_partial_shipment():
    """Product qty=100, only 50 accepted → not ready."""
    try:
        async with async_session_factory() as session:
            client = Client(code="TSTPRFTR1", full_name="Ready Partial")
            mgr = User(login="prftr1_mgr", password_hash=hash_password("x"), role=UserRole.manager, full_name="RMgr1")
            adm = User(login="prftr1_adm", password_hash=hash_password("x"), role=UserRole.admin, full_name="RAdm1")
            sup = Supplier(name="PrftSupplierR1")
            session.add_all([client, mgr, adm, sup])
            await session.commit()
            for o in (client, mgr, adm, sup):
                await session.refresh(o)
            order = Order(number="TSTPRFTR1-1", client_id=client.id, manager_id=mgr.id,
                          status=OrderStatus.in_progress, currency="RUB")
            session.add(order)
            await session.commit()
            await session.refresh(order)

            product = Product(order_id=order.id, supplier_id=sup.id, name="G",
                              quantity=Decimal("100.000"), price=Decimal("10.00"), currency="RUB")
            session.add(product)
            await session.commit()
            await session.refresh(product)

            # Only 50 accepted out of 100
            await add_shipment(
                            session,
                            lines=[(product.id, Decimal("50.000"))],
                            order_id=order.id,
                            created_by_id=adm.id,
                            tracking="R1-TRK",
                            ship_date=_NOW,
                            status=LogisticsStatus.accepted,
                            expense_amount=Decimal("0.00"),
                            currency="RUB",
                            exchange_rate=Decimal("1.000000"),
                        )
            await session.commit()

        async with async_session_factory() as session:
            b = await calculate_profit(order.id, session)

        assert b.is_ready is False
    finally:
        await _cleanup("TSTPRFTR1", ["prftr1_mgr", "prftr1_adm"])


@pytest.mark.asyncio
async def test_readiness_true_fully_shipped_and_accepted():
    """Product qty=50, all 50 accepted, no in_transit → ready."""
    try:
        async with async_session_factory() as session:
            client = Client(code="TSTPRFTR2", full_name="Ready Full")
            mgr = User(login="prftr2_mgr", password_hash=hash_password("x"), role=UserRole.manager, full_name="RMgr2")
            adm = User(login="prftr2_adm", password_hash=hash_password("x"), role=UserRole.admin, full_name="RAdm2")
            sup = Supplier(name="PrftSupplierR2")
            session.add_all([client, mgr, adm, sup])
            await session.commit()
            for o in (client, mgr, adm, sup):
                await session.refresh(o)
            order = Order(number="TSTPRFTR2-1", client_id=client.id, manager_id=mgr.id,
                          status=OrderStatus.in_progress, currency="RUB")
            session.add(order)
            await session.commit()
            await session.refresh(order)

            product = Product(order_id=order.id, supplier_id=sup.id, name="G",
                              quantity=Decimal("50.000"), price=Decimal("10.00"), currency="RUB")
            session.add(product)
            await session.commit()
            await session.refresh(product)

            # Exactly 50 accepted
            await add_shipment(
                            session,
                            lines=[(product.id, Decimal("50.000"))],
                            order_id=order.id,
                            created_by_id=adm.id,
                            tracking="R2-TRK",
                            ship_date=_NOW,
                            status=LogisticsStatus.accepted,
                            expense_amount=Decimal("0.00"),
                            currency="RUB",
                            exchange_rate=Decimal("1.000000"),
                        )
            await session.commit()

        async with async_session_factory() as session:
            b = await calculate_profit(order.id, session)

        assert b.is_ready is True
    finally:
        await _cleanup("TSTPRFTR2", ["prftr2_mgr", "prftr2_adm"])


@pytest.mark.asyncio
async def test_readiness_false_in_transit_blocks_even_if_qty_covered():
    """Qty fully covered (accepted ≥ product.qty) but one entry still in_transit → not ready."""
    try:
        async with async_session_factory() as session:
            client = Client(code="TSTPRFTR3", full_name="Ready InTransit")
            mgr = User(login="prftr3_mgr", password_hash=hash_password("x"), role=UserRole.manager, full_name="RMgr3")
            adm = User(login="prftr3_adm", password_hash=hash_password("x"), role=UserRole.admin, full_name="RAdm3")
            sup = Supplier(name="PrftSupplierR3")
            session.add_all([client, mgr, adm, sup])
            await session.commit()
            for o in (client, mgr, adm, sup):
                await session.refresh(o)
            order = Order(number="TSTPRFTR3-1", client_id=client.id, manager_id=mgr.id,
                          status=OrderStatus.in_progress, currency="RUB")
            session.add(order)
            await session.commit()
            await session.refresh(order)

            product = Product(order_id=order.id, supplier_id=sup.id, name="G",
                              quantity=Decimal("30.000"), price=Decimal("10.00"), currency="RUB")
            session.add(product)
            await session.commit()
            await session.refresh(product)

            # 30 accepted (covers qty) but another 10 still in_transit
            await add_shipment(
                session,
                lines=[(product.id, Decimal("30.000"))],
                order_id=order.id,
                created_by_id=adm.id,
                tracking="R3-TRK-A",
                ship_date=_NOW,
                status=LogisticsStatus.accepted,
                expense_amount=Decimal("0.00"),
                currency="RUB",
                exchange_rate=Decimal("1.000000"),
            )
            await add_shipment(
                session,
                lines=[(product.id, Decimal("10.000"))],
                order_id=order.id,
                created_by_id=mgr.id,
                tracking="R3-TRK-B",
                ship_date=_NOW,
                status=LogisticsStatus.in_transit,
            )
            await session.commit()

        async with async_session_factory() as session:
            b = await calculate_profit(order.id, session)

        assert b.is_ready is False  # in_transit present even though qty is covered
    finally:
        await _cleanup("TSTPRFTR3", ["prftr3_mgr", "prftr3_adm"])
