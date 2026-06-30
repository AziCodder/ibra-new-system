from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.client import Client
from app.models.logistics import Logistics, LogisticsStatus
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.routers.logistics import (
    accept_logistics,
    create_logistics,
    delete_logistics,
    get_logistics,
    list_logistics,
    unaccept_logistics,
    update_logistics,
)
from app.schemas.logistics import LogisticsAccept, LogisticsCreate, LogisticsUpdate

SHIP_DATE = datetime.now(UTC)


async def _setup():
    async with async_session_factory() as session:
        client = Client(code="TSTLGC", full_name="Logistics CRUD Client")
        supplier = Supplier(name="Logistics CRUD Supplier")
        owner = User(login="lgc_owner", password_hash=hash_password("x"), role=UserRole.manager, full_name="Owner Manager")
        other = User(login="lgc_other", password_hash=hash_password("x"), role=UserRole.manager, full_name="Other Manager")
        observer = User(login="lgc_observer", password_hash=hash_password("x"), role=UserRole.observer, full_name="Observer")
        admin = User(login="lgc_admin", password_hash=hash_password("x"), role=UserRole.admin, full_name="Admin")
        session.add_all([client, supplier, owner, other, observer, admin])
        await session.commit()
        for obj in (client, supplier, owner, other, observer, admin):
            await session.refresh(obj)

        order = Order(
            number=f"{client.code}-1",
            client_id=client.id,
            manager_id=owner.id,
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

        return client, supplier, owner, other, observer, admin, order, product


async def _cleanup(client_id: int, supplier_id: int, user_ids: list[int]):
    async with async_session_factory() as session:
        order_ids = select(Order.id).where(Order.client_id == client_id)
        await session.execute(delete(Logistics).where(Logistics.order_id.in_(order_ids)))
        await session.execute(delete(Product).where(Product.order_id.in_(order_ids)))
        await session.execute(delete(Order).where(Order.client_id == client_id))
        await session.execute(delete(Client).where(Client.id == client_id))
        await session.execute(delete(Supplier).where(Supplier.id == supplier_id))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_create_list_get_update_delete_lifecycle():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_logistics(
                order.id,
                LogisticsCreate(product_id=product.id, quantity=Decimal("10"), tracking="M77-170566", ship_date=SHIP_DATE),
                owner,
                session,
            )
            assert created.quantity == Decimal("10")
            assert created.status == LogisticsStatus.in_transit
            assert created.product_name == "Widget"
            assert created.created_by_name == "Owner Manager"

        async with async_session_factory() as session:
            listed = await list_logistics(order.id, owner, session)
            assert len(listed) == 1

        async with async_session_factory() as session:
            fetched = await get_logistics(order.id, created.id, owner, session)
            assert fetched.tracking == "M77-170566"

        async with async_session_factory() as session:
            updated = await update_logistics(
                order.id, created.id, LogisticsUpdate(tracking="UPDATED-CODE"), owner, session
            )
            assert updated.tracking == "UPDATED-CODE"

        async with async_session_factory() as session:
            await delete_logistics(order.id, created.id, owner, session)

        async with async_session_factory() as session:
            listed = await list_logistics(order.id, owner, session)
            assert listed == []
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_create_rejects_quantity_exceeding_remaining_with_422():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_logistics(
                    order.id,
                    LogisticsCreate(product_id=product.id, quantity=Decimal("999"), ship_date=SHIP_DATE),
                    owner,
                    session,
                )
            assert exc_info.value.status_code == 422
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_create_rejects_product_from_another_order_with_422():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            foreign_order = Order(
                number="FOREIGN-1", client_id=client.id, manager_id=owner.id, status=OrderStatus.in_progress, currency="USD"
            )
            session.add(foreign_order)
            await session.commit()
            await session.refresh(foreign_order)

            with pytest.raises(HTTPException) as exc_info:
                await create_logistics(
                    foreign_order.id,
                    LogisticsCreate(product_id=product.id, quantity=Decimal("1"), ship_date=SHIP_DATE),
                    owner,
                    session,
                )
            assert exc_info.value.status_code == 422

            await session.execute(delete(Order).where(Order.id == foreign_order.id))
            await session.commit()
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_manager_cannot_access_other_managers_logistics():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await list_logistics(order.id, other, session)
            assert exc_info.value.status_code == 404

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_logistics(
                    order.id,
                    LogisticsCreate(product_id=product.id, quantity=Decimal("1"), ship_date=SHIP_DATE),
                    other,
                    session,
                )
            assert exc_info.value.status_code == 404
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_observer_can_read_but_not_create():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            await create_logistics(
                order.id,
                LogisticsCreate(product_id=product.id, quantity=Decimal("1"), ship_date=SHIP_DATE),
                owner,
                session,
            )

        async with async_session_factory() as session:
            listed = await list_logistics(order.id, observer, session)
            assert len(listed) == 1

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_logistics(
                    order.id,
                    LogisticsCreate(product_id=product.id, quantity=Decimal("1"), ship_date=SHIP_DATE),
                    observer,
                    session,
                )
            assert exc_info.value.status_code == 403
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_manager_cannot_edit_accepted_logistics():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_logistics(
                order.id,
                LogisticsCreate(
                    product_id=product.id,
                    quantity=Decimal("5"),
                    ship_date=SHIP_DATE,
                    status=LogisticsStatus.accepted,
                ),
                admin,
                session,
            )

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await update_logistics(order.id, created.id, LogisticsUpdate(tracking="X"), owner, session)
            assert exc_info.value.status_code == 403
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_admin_can_edit_accepted_logistics():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_logistics(
                order.id,
                LogisticsCreate(
                    product_id=product.id,
                    quantity=Decimal("5"),
                    ship_date=SHIP_DATE,
                    status=LogisticsStatus.accepted,
                ),
                admin,
                session,
            )

        async with async_session_factory() as session:
            updated = await update_logistics(order.id, created.id, LogisticsUpdate(tracking="ADMIN-EDIT"), admin, session)
            assert updated.tracking == "ADMIN-EDIT"
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_delete_blocked_unless_in_transit_for_any_role():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_logistics(
                order.id,
                LogisticsCreate(
                    product_id=product.id,
                    quantity=Decimal("5"),
                    ship_date=SHIP_DATE,
                    status=LogisticsStatus.accepted,
                ),
                admin,
                session,
            )

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await delete_logistics(order.id, created.id, admin, session)
            assert exc_info.value.status_code == 403
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_admin_can_accept_in_transit_shipment():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_logistics(
                order.id,
                LogisticsCreate(product_id=product.id, quantity=Decimal("5"), ship_date=SHIP_DATE),
                owner,
                session,
            )

        async with async_session_factory() as session:
            accepted = await accept_logistics(
                order.id,
                created.id,
                LogisticsAccept(
                    received_date=SHIP_DATE,
                    expense_amount=Decimal("100.00"),
                    currency="USD",
                    exchange_rate=Decimal("1.0"),
                    note="Arrived fine",
                ),
                admin,
                session,
            )
            assert accepted.status == LogisticsStatus.accepted
            assert accepted.received_date == SHIP_DATE
            assert accepted.expense_amount == Decimal("100.00")
            assert accepted.currency == "USD"
            assert accepted.exchange_rate == Decimal("1.0")
            assert accepted.acceptance_note == "Arrived fine"
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_manager_cannot_accept_shipment():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_logistics(
                order.id,
                LogisticsCreate(product_id=product.id, quantity=Decimal("5"), ship_date=SHIP_DATE),
                owner,
                session,
            )

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await accept_logistics(
                    order.id,
                    created.id,
                    LogisticsAccept(
                        received_date=SHIP_DATE,
                        expense_amount=Decimal("100.00"),
                        currency="USD",
                        exchange_rate=Decimal("1.0"),
                    ),
                    owner,
                    session,
                )
            assert exc_info.value.status_code == 403
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_accept_rejects_non_in_transit_shipment_with_409():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_logistics(
                order.id,
                LogisticsCreate(
                    product_id=product.id,
                    quantity=Decimal("5"),
                    ship_date=SHIP_DATE,
                    status=LogisticsStatus.accepted,
                ),
                admin,
                session,
            )

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await accept_logistics(
                    order.id,
                    created.id,
                    LogisticsAccept(
                        received_date=SHIP_DATE,
                        expense_amount=Decimal("50.00"),
                        currency="USD",
                        exchange_rate=Decimal("1.0"),
                    ),
                    admin,
                    session,
                )
            assert exc_info.value.status_code == 409
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_admin_can_unaccept_and_clears_receipt_fields():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_logistics(
                order.id,
                LogisticsCreate(product_id=product.id, quantity=Decimal("5"), ship_date=SHIP_DATE),
                owner,
                session,
            )

        async with async_session_factory() as session:
            await accept_logistics(
                order.id,
                created.id,
                LogisticsAccept(
                    received_date=SHIP_DATE,
                    expense_amount=Decimal("100.00"),
                    currency="USD",
                    exchange_rate=Decimal("1.0"),
                    note="Arrived fine",
                ),
                admin,
                session,
            )

        async with async_session_factory() as session:
            unaccepted = await unaccept_logistics(order.id, created.id, admin, session)
            assert unaccepted.status == LogisticsStatus.in_transit
            assert unaccepted.received_date is None
            assert unaccepted.expense_amount is None
            assert unaccepted.currency is None
            assert unaccepted.exchange_rate is None
            assert unaccepted.acceptance_note is None
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_manager_cannot_unaccept_shipment():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_logistics(
                order.id,
                LogisticsCreate(
                    product_id=product.id,
                    quantity=Decimal("5"),
                    ship_date=SHIP_DATE,
                    status=LogisticsStatus.accepted,
                ),
                admin,
                session,
            )

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await unaccept_logistics(order.id, created.id, owner, session)
            assert exc_info.value.status_code == 403
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_unaccept_rejects_non_accepted_shipment_with_409():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_logistics(
                order.id,
                LogisticsCreate(product_id=product.id, quantity=Decimal("5"), ship_date=SHIP_DATE),
                owner,
                session,
            )

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await unaccept_logistics(order.id, created.id, admin, session)
            assert exc_info.value.status_code == 409
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_reaccept_after_unaccept_round_trip():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_logistics(
                order.id,
                LogisticsCreate(product_id=product.id, quantity=Decimal("5"), ship_date=SHIP_DATE),
                owner,
                session,
            )

        async with async_session_factory() as session:
            await accept_logistics(
                order.id,
                created.id,
                LogisticsAccept(
                    received_date=SHIP_DATE,
                    expense_amount=Decimal("100.00"),
                    currency="USD",
                    exchange_rate=Decimal("1.0"),
                ),
                admin,
                session,
            )

        async with async_session_factory() as session:
            await unaccept_logistics(order.id, created.id, admin, session)

        async with async_session_factory() as session:
            reaccepted = await accept_logistics(
                order.id,
                created.id,
                LogisticsAccept(
                    received_date=SHIP_DATE,
                    expense_amount=Decimal("75.00"),
                    currency="EUR",
                    exchange_rate=Decimal("0.9"),
                    note="Second time",
                ),
                admin,
                session,
            )
            assert reaccepted.status == LogisticsStatus.accepted
            assert reaccepted.expense_amount == Decimal("75.00")
            assert reaccepted.currency == "EUR"
            assert reaccepted.acceptance_note == "Second time"
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_update_rejects_status_accepted_with_422():
    client, supplier, owner, other, observer, admin, order, product = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_logistics(
                order.id,
                LogisticsCreate(product_id=product.id, quantity=Decimal("5"), ship_date=SHIP_DATE),
                owner,
                session,
            )

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await update_logistics(
                    order.id, created.id, LogisticsUpdate(status=LogisticsStatus.accepted), admin, session
                )
            assert exc_info.value.status_code == 422
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])
