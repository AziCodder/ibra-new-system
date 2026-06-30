from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.client import Client
from app.models.ledger_entry import LedgerEntry, LedgerEntryType
from app.models.order import Order, OrderStatus
from app.models.user import User, UserRole
from app.routers.ledger_entries import create_ledger_entry, delete_ledger_entry, list_ledger_entries
from app.schemas.ledger_entry import LedgerEntryCreate


async def _setup():
    async with async_session_factory() as session:
        client = Client(code="TSTLED2", full_name="Ledger API Client")
        owner = User(login="lda_owner", password_hash=hash_password("x"), role=UserRole.manager, full_name="Owner Manager")
        other = User(login="lda_other", password_hash=hash_password("x"), role=UserRole.manager, full_name="Other Manager")
        observer = User(login="lda_observer", password_hash=hash_password("x"), role=UserRole.observer, full_name="Observer")
        admin = User(login="lda_admin", password_hash=hash_password("x"), role=UserRole.admin, full_name="Admin")
        session.add_all([client, owner, other, observer, admin])
        await session.commit()
        for obj in (client, owner, other, observer, admin):
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

        return client, owner, other, observer, admin, order


async def _cleanup(client_id: int, user_ids: list[int]):
    async with async_session_factory() as session:
        order_ids = select(Order.id).where(Order.client_id == client_id)
        await session.execute(delete(LedgerEntry).where(LedgerEntry.order_id.in_(order_ids)))
        await session.execute(delete(Order).where(Order.client_id == client_id))
        await session.execute(delete(Client).where(Client.id == client_id))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_create_list_delete_lifecycle():
    client, owner, other, observer, admin, order = await _setup()
    try:
        async with async_session_factory() as session:
            income = await create_ledger_entry(
                order.id,
                LedgerEntryCreate(type=LedgerEntryType.income, amount=Decimal("100.00"), currency="USD", exchange_rate=Decimal("1.0"), details="Advance"),
                owner,
                session,
            )
            assert income.type == LedgerEntryType.income
            assert income.author_name == "Owner Manager"

        async with async_session_factory() as session:
            expense = await create_ledger_entry(
                order.id,
                LedgerEntryCreate(type=LedgerEntryType.expense, amount=Decimal("30.00"), currency="USD", exchange_rate=Decimal("1.0"), details="Fee"),
                owner,
                session,
            )
            assert expense.type == LedgerEntryType.expense

        async with async_session_factory() as session:
            listed = await list_ledger_entries(order.id, owner, session)
            assert len(listed) == 2

        async with async_session_factory() as session:
            await delete_ledger_entry(order.id, income.id, owner, session)

        async with async_session_factory() as session:
            listed = await list_ledger_entries(order.id, owner, session)
            assert len(listed) == 1
            assert listed[0].type == LedgerEntryType.expense
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_manager_cannot_access_other_managers_ledger():
    client, owner, other, observer, admin, order = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await list_ledger_entries(order.id, other, session)
            assert exc_info.value.status_code == 404

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_ledger_entry(
                    order.id,
                    LedgerEntryCreate(type=LedgerEntryType.income, amount=Decimal("10.00"), currency="USD", exchange_rate=Decimal("1.0")),
                    other,
                    session,
                )
            assert exc_info.value.status_code == 404
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_observer_can_read_but_not_create_or_delete():
    client, owner, other, observer, admin, order = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_ledger_entry(
                order.id,
                LedgerEntryCreate(type=LedgerEntryType.income, amount=Decimal("10.00"), currency="USD", exchange_rate=Decimal("1.0")),
                owner,
                session,
            )

        async with async_session_factory() as session:
            listed = await list_ledger_entries(order.id, observer, session)
            assert len(listed) == 1

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_ledger_entry(
                    order.id,
                    LedgerEntryCreate(type=LedgerEntryType.expense, amount=Decimal("5.00"), currency="USD", exchange_rate=Decimal("1.0")),
                    observer,
                    session,
                )
            assert exc_info.value.status_code == 403

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await delete_ledger_entry(order.id, created.id, observer, session)
            assert exc_info.value.status_code == 403
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_admin_can_create_and_delete_on_any_order():
    client, owner, other, observer, admin, order = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_ledger_entry(
                order.id,
                LedgerEntryCreate(type=LedgerEntryType.expense, amount=Decimal("20.00"), currency="USD", exchange_rate=Decimal("1.0")),
                admin,
                session,
            )

        async with async_session_factory() as session:
            await delete_ledger_entry(order.id, created.id, admin, session)

        async with async_session_factory() as session:
            listed = await list_ledger_entries(order.id, admin, session)
            assert listed == []
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_delete_nonexistent_entry_returns_404():
    client, owner, other, observer, admin, order = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await delete_ledger_entry(order.id, 999999, owner, session)
            assert exc_info.value.status_code == 404
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_router_has_no_patch_or_put_route():
    from app.routers.ledger_entries import router

    methods = set()
    for route in router.routes:
        methods.update(route.methods or set())
    assert "PATCH" not in methods
    assert "PUT" not in methods


@pytest.mark.asyncio
async def test_app_returns_405_for_patch_on_ledger_entry():
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    client, owner, other, observer, admin, order = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_ledger_entry(
                order.id,
                LedgerEntryCreate(type=LedgerEntryType.income, amount=Decimal("10.00"), currency="USD", exchange_rate=Decimal("1.0")),
                owner,
                session,
            )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.patch(f"/api/orders/{order.id}/ledger-entries/{created.id}", json={"details": "x"})
            assert response.status_code == 405
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id, admin.id])
