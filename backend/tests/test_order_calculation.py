"""Order calculation (правки 2026-10-01 п.4): an admin shares a completed order's
profit between staff by percentage, which freezes the whole order — for every
role, admin included — until the calculation is cancelled."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.action_log import ActionLog
from app.models.client import Client
from app.models.ledger_entry import LedgerEntry, LedgerEntryType
from app.models.logistics import Logistics, LogisticsStatus
from app.models.note import Note
from app.models.order import Order, OrderStatus
from app.models.order_calculation import OrderCalculationParticipant
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest, PaymentRequestItem
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.routers.logistics import create_logistics_comment
from app.routers.notes import create_note
from app.routers.order_calculation import (
    calculate_order,
    cancel_calculation,
    get_calculation,
    split_profit,
)
from app.routers.orders import OrderStatusIn, add_order_file, list_orders, set_order_status, update_order
from app.routers.products import create_product
from app.routers.users import list_staff
from app.schemas.logistics_comment import LogisticsCommentCreate
from app.schemas.note import NoteCreate
from app.schemas.order import OrderFileAdd, OrderUpdate
from app.schemas.order_calculation import CalculationIn, CalculationParticipantIn
from app.schemas.product import ProductCreate
from app.services.order_access import ORDER_CALCULATED_DETAIL
from tests.helpers import add_shipment

SHIP_DATE = datetime.now(UTC)


async def _setup():
    """A completed USD order: income 1 000, goods 200 bought and paid → profit 800."""
    async with async_session_factory() as session:
        client = Client(code="TSTCALC", full_name="Calculation Client")
        supplier = Supplier(name="Calculation Supplier")
        admin = User(login="calc_admin", password_hash=hash_password("x"), role=UserRole.admin, full_name="Ибрагим")
        mgr1 = User(login="calc_mgr1", password_hash=hash_password("x"), role=UserRole.manager, full_name="Могамед")
        mgr2 = User(login="calc_mgr2", password_hash=hash_password("x"), role=UserRole.manager, full_name="Глеб")
        observer = User(login="calc_obs", password_hash=hash_password("x"), role=UserRole.observer, full_name="Obs")
        session.add_all([client, supplier, admin, mgr1, mgr2, observer])
        await session.commit()
        for obj in (client, supplier, admin, mgr1, mgr2, observer):
            await session.refresh(obj)

        order = Order(number="TSTCALC-1", client_id=client.id, manager_id=mgr1.id,
                      status=OrderStatus.in_progress, currency="USD")
        session.add(order)
        await session.commit()
        await session.refresh(order)

        product = Product(order_id=order.id, supplier_id=supplier.id, name="Widget",
                          quantity=Decimal("10.000"), price=Decimal("20.00"), currency="USD")
        session.add(product)
        await session.commit()
        await session.refresh(product)

        await add_shipment(session, lines=[(product.id, Decimal("10.000"))], order_id=order.id,
                           created_by_id=admin.id, tracking="CALC-TRK", ship_date=SHIP_DATE,
                           status=LogisticsStatus.accepted, currency="USD", exchange_rate=Decimal("1"))
        pr = PaymentRequest(order_id=order.id, created_by_id=admin.id)
        session.add(pr)
        await session.commit()
        await session.refresh(pr)
        session.add(PaymentRequestItem(payment_request_id=pr.id, product_id=product.id, amount=Decimal("200.00")))
        session.add(Payment(payment_request_id=pr.id, author_id=admin.id, amount=Decimal("200.00"),
                            currency="USD", exchange_rate=Decimal("1")))
        session.add(LedgerEntry(order_id=order.id, author_id=admin.id, type=LedgerEntryType.income,
                                amount=Decimal("1000.00"), currency="USD", exchange_rate=Decimal("1")))
        await session.commit()

    async with async_session_factory() as session:
        await set_order_status(order.id, OrderStatusIn(status=OrderStatus.completed), admin, session)

    return client, supplier, admin, mgr1, mgr2, observer, order, product


async def _cleanup(client_id: int, supplier_id: int, user_ids: list[int]):
    async with async_session_factory() as session:
        order_ids = select(Order.id).where(Order.client_id == client_id)
        request_ids = select(PaymentRequest.id).where(PaymentRequest.order_id.in_(order_ids))
        await session.execute(delete(OrderCalculationParticipant).where(OrderCalculationParticipant.order_id.in_(order_ids)))
        await session.execute(delete(Payment).where(Payment.payment_request_id.in_(request_ids)))
        await session.execute(delete(PaymentRequestItem).where(PaymentRequestItem.payment_request_id.in_(request_ids)))
        await session.execute(delete(PaymentRequest).where(PaymentRequest.order_id.in_(order_ids)))
        await session.execute(delete(LedgerEntry).where(LedgerEntry.order_id.in_(order_ids)))
        await session.execute(delete(Logistics).where(Logistics.order_id.in_(order_ids)))
        await session.execute(delete(Note).where(Note.order_id.in_(order_ids)))
        await session.execute(delete(Product).where(Product.order_id.in_(order_ids)))
        await session.execute(delete(Order).where(Order.client_id == client_id))
        await session.execute(delete(Client).where(Client.id == client_id))
        await session.execute(delete(Supplier).where(Supplier.id == supplier_id))
        await session.execute(delete(ActionLog).where(ActionLog.actor_id.in_(user_ids)))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


def _split(*pairs: tuple[int, str]) -> CalculationIn:
    return CalculationIn(
        participants=[CalculationParticipantIn(user_id=user_id, percent=Decimal(pct)) for user_id, pct in pairs]
    )


async def _calculate(order_id: int, admin: User, body: CalculationIn):
    async with async_session_factory() as session:
        return await calculate_order(order_id, body, admin, session)


async def _expect(status_code: int, coro) -> HTTPException:
    with pytest.raises(HTTPException) as exc_info:
        await coro
    assert exc_info.value.status_code == status_code
    return exc_info.value


def test_split_profit_lands_the_rounding_remainder_on_the_last_share():
    third = [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")]
    assert split_profit(Decimal("100.00"), third) == [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")]
    assert split_profit(Decimal("0.10"), third) == [Decimal("0.03"), Decimal("0.03"), Decimal("0.04")]
    halves = split_profit(Decimal("0.01"), [Decimal("50"), Decimal("50")])
    assert sum(halves) == Decimal("0.01")


def test_participant_count_is_bounded_by_the_schema():
    with pytest.raises(ValidationError):
        CalculationIn(participants=[CalculationParticipantIn(user_id=1, percent=Decimal("100"))])
    with pytest.raises(ValidationError):
        CalculationIn(
            participants=[CalculationParticipantIn(user_id=i, percent=Decimal("16")) for i in range(1, 7)]
        )


@pytest.mark.asyncio
async def test_calculation_shares_profit_and_marks_the_order():
    client, supplier, admin, mgr1, mgr2, observer, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            before = await get_calculation(order.id, mgr1, session)
        assert before.is_calculated is False
        assert before.is_ready is True
        assert before.profit == Decimal("800.00")

        result = await _calculate(order.id, admin, _split((admin.id, "40"), (mgr1.id, "40"), (mgr2.id, "20")))
        assert result.is_calculated is True
        assert result.profit == Decimal("800.00")
        assert [(p.full_name, p.percent, p.amount) for p in result.participants] == [
            ("Ибрагим", Decimal("40.00"), Decimal("320.00")),
            ("Могамед", Decimal("40.00"), Decimal("320.00")),
            ("Глеб", Decimal("20.00"), Decimal("160.00")),
        ]

        # A manager reads the calculation of their own order.
        async with async_session_factory() as session:
            seen = await get_calculation(order.id, mgr1, session)
        assert seen.is_calculated is True
        assert len(seen.participants) == 3

        async with async_session_factory() as session:
            calculated = await list_orders(
                client_id=client.id, is_calculated=True, page=1, page_size=20, user=admin, session=session
            )
            not_calculated = await list_orders(
                client_id=client.id, is_calculated=False, page=1, page_size=20, user=admin, session=session
            )
        assert [o.id for o in calculated.items] == [order.id]
        assert calculated.items[0].is_calculated is True
        assert not_calculated.items == []
    finally:
        await _cleanup(client.id, supplier.id, [admin.id, mgr1.id, mgr2.id, observer.id])


@pytest.mark.asyncio
async def test_calculation_rejects_a_bad_split():
    client, supplier, admin, mgr1, mgr2, observer, order, product = await _setup()
    try:
        error = await _expect(422, _calculate(order.id, admin, _split((admin.id, "50"), (mgr1.id, "40"))))
        assert error.detail == "Сумма процентов участников должна быть ровно 100"

        error = await _expect(422, _calculate(order.id, admin, _split((mgr1.id, "50"), (mgr1.id, "50"))))
        assert error.detail == "Каждого участника можно добавить только один раз"

        error = await _expect(422, _calculate(order.id, admin, _split((mgr1.id, "50"), (observer.id, "50"))))
        assert error.detail == "Участниками могут быть только администраторы и менеджеры"

        async with async_session_factory() as session:
            still = await get_calculation(order.id, admin, session)
        assert still.is_calculated is False
    finally:
        await _cleanup(client.id, supplier.id, [admin.id, mgr1.id, mgr2.id, observer.id])


@pytest.mark.asyncio
async def test_only_a_completed_order_can_be_calculated_and_only_once():
    client, supplier, admin, mgr1, mgr2, observer, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            await set_order_status(order.id, OrderStatusIn(status=OrderStatus.in_progress), admin, session)
        await _expect(409, _calculate(order.id, admin, _split((admin.id, "50"), (mgr1.id, "50"))))

        async with async_session_factory() as session:
            await set_order_status(order.id, OrderStatusIn(status=OrderStatus.completed), admin, session)
        await _calculate(order.id, admin, _split((admin.id, "50"), (mgr1.id, "50")))
        await _expect(409, _calculate(order.id, admin, _split((admin.id, "50"), (mgr2.id, "50"))))
    finally:
        await _cleanup(client.id, supplier.id, [admin.id, mgr1.id, mgr2.id, observer.id])


@pytest.mark.asyncio
async def test_calculated_order_is_frozen_even_for_admin():
    client, supplier, admin, mgr1, mgr2, observer, order, product = await _setup()
    try:
        await _calculate(order.id, admin, _split((admin.id, "50"), (mgr1.id, "50")))

        async with async_session_factory() as session:
            logistics_id = (
                await session.execute(select(Logistics.id).where(Logistics.order_id == order.id))
            ).scalar_one()

        attempts = [
            lambda s: create_note(order.id, NoteCreate(text="late note"), admin, s),
            lambda s: create_logistics_comment(order.id, logistics_id, LogisticsCommentCreate(text="late"), admin, s),
            lambda s: set_order_status(order.id, OrderStatusIn(status=OrderStatus.in_progress), admin, s),
            lambda s: update_order(order.id, OrderUpdate(details="edited"), admin, s),
            lambda s: add_order_file(order.id, OrderFileAdd(file_key="late.pdf"), admin, s),
            lambda s: create_product(
                order.id,
                ProductCreate(supplier_id=supplier.id, name="Late", quantity=Decimal("1"), price=Decimal("1")),
                admin,
                s,
            ),
        ]
        for attempt in attempts:
            async with async_session_factory() as session:
                error = await _expect(409, attempt(session))
            assert error.detail == ORDER_CALCULATED_DETAIL
    finally:
        await _cleanup(client.id, supplier.id, [admin.id, mgr1.id, mgr2.id, observer.id])


@pytest.mark.asyncio
async def test_cancelling_the_calculation_unfreezes_the_order():
    client, supplier, admin, mgr1, mgr2, observer, order, product = await _setup()
    try:
        await _calculate(order.id, admin, _split((admin.id, "50"), (mgr1.id, "50")))

        async with async_session_factory() as session:
            await cancel_calculation(order.id, admin, session)

        async with async_session_factory() as session:
            after = await get_calculation(order.id, admin, session)
            leftover = (
                await session.execute(
                    select(OrderCalculationParticipant).where(OrderCalculationParticipant.order_id == order.id)
                )
            ).scalars().all()
        assert after.is_calculated is False
        assert after.participants == []
        assert leftover == []

        async with async_session_factory() as session:
            note = await create_note(order.id, NoteCreate(text="after cancel"), admin, session)
        assert note.text == "after cancel"

        async with async_session_factory() as session:
            reverted = await set_order_status(
                order.id, OrderStatusIn(status=OrderStatus.in_progress), admin, session
            )
        assert reverted.status == OrderStatus.in_progress

        # Cancelling an order that isn't calculated is a harmless no-op.
        async with async_session_factory() as session:
            await cancel_calculation(order.id, admin, session)
    finally:
        await _cleanup(client.id, supplier.id, [admin.id, mgr1.id, mgr2.id, observer.id])


@pytest.mark.asyncio
async def test_staff_list_has_admins_and_managers_but_not_observers():
    client, supplier, admin, mgr1, mgr2, observer, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            staff = await list_staff(observer, session)
        ids = {u.id for u in staff}
        assert {admin.id, mgr1.id, mgr2.id} <= ids
        assert observer.id not in ids
    finally:
        await _cleanup(client.id, supplier.id, [admin.id, mgr1.id, mgr2.id, observer.id])
