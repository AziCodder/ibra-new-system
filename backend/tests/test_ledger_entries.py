from decimal import Decimal

import pytest
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.models.client import Client
from app.models.ledger_entry import LedgerEntry, LedgerEntryType
from app.models.order import Order, OrderStatus
from app.models.user import User, UserRole
from app.services.order_dependencies import count_order_dependencies


async def _setup():
    async with async_session_factory() as session:
        client = Client(code="TSTLED", full_name="Ledger Test Client")
        session.add(client)
        await session.commit()
        await session.refresh(client)

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

        return client, admin, order


async def _cleanup(client_id: int):
    async with async_session_factory() as session:
        order_ids = select(Order.id).where(Order.client_id == client_id)
        await session.execute(delete(LedgerEntry).where(LedgerEntry.order_id.in_(order_ids)))
        await session.execute(delete(Order).where(Order.client_id == client_id))
        await session.execute(delete(Client).where(Client.id == client_id))
        await session.commit()


@pytest.mark.asyncio
async def test_ledger_entry_persists_with_fixed_type():
    client, admin, order = await _setup()
    try:
        async with async_session_factory() as session:
            entry = LedgerEntry(
                order_id=order.id,
                author_id=admin.id,
                type=LedgerEntryType.income,
                amount=Decimal("1000.00"),
                currency="USD",
                exchange_rate=Decimal("1"),
                details="Client payment",
            )
            session.add(entry)
            await session.commit()
            await session.refresh(entry)

            assert entry.type == LedgerEntryType.income
            assert entry.amount == Decimal("1000.00")
            assert entry.created_at is not None

        async with async_session_factory() as session:
            persisted = (await session.execute(select(LedgerEntry).where(LedgerEntry.id == entry.id))).scalar_one()
            assert persisted.type == LedgerEntryType.income
    finally:
        await _cleanup(client.id)


@pytest.mark.asyncio
async def test_ledger_entry_expense_type_persists():
    client, admin, order = await _setup()
    try:
        async with async_session_factory() as session:
            entry = LedgerEntry(
                order_id=order.id,
                author_id=admin.id,
                type=LedgerEntryType.expense,
                amount=Decimal("50.00"),
                currency="USD",
                exchange_rate=Decimal("1"),
                details="Packaging",
            )
            session.add(entry)
            await session.commit()
            await session.refresh(entry)

            assert entry.type == LedgerEntryType.expense
    finally:
        await _cleanup(client.id)


@pytest.mark.asyncio
async def test_count_order_dependencies_counts_ledger_entries():
    client, admin, order = await _setup()
    try:
        async with async_session_factory() as session:
            count = await count_order_dependencies(session, order.id)
            assert count == 0

            session.add(
                LedgerEntry(
                    order_id=order.id,
                    author_id=admin.id,
                    type=LedgerEntryType.income,
                    amount=Decimal("100.00"),
                    currency="USD",
                    exchange_rate=Decimal("1"),
                )
            )
            await session.commit()

        async with async_session_factory() as session:
            count = await count_order_dependencies(session, order.id)
            assert count == 1
    finally:
        await _cleanup(client.id)
