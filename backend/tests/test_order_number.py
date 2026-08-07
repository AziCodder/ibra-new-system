import asyncio

import pytest
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.models.client import Client
from app.models.order import Order, OrderStatus
from app.models.user import User
from app.services.order_number import generate_order_number


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
async def test_order_numbers_sequential_under_concurrency():
    async with async_session_factory() as session:
        client = Client(code="TST99", full_name="Test Client")
        session.add(client)
        await session.commit()
        await session.refresh(client)

        manager_result = await session.execute(select(User).limit(1))
        manager = manager_result.scalar_one()

    try:
        numbers = await asyncio.gather(
            _create_order_with_number(client.id, manager.id),
            _create_order_with_number(client.id, manager.id),
        )
        assert sorted(numbers) == ["TST99-1", "TST99-2"]
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(Order).where(Order.client_id == client.id))
            await session.execute(delete(Client).where(Client.id == client.id))
            await session.commit()


@pytest.mark.asyncio
async def test_deleting_an_order_does_not_make_the_next_one_reuse_its_number():
    """Regression: numbering counted existing orders, so deleting one handed the
    next order a number that was already taken — orders.number is unique, so the
    client could never get another order created."""
    async with async_session_factory() as session:
        client = Client(code="TST98", full_name="Gap Client")
        session.add(client)
        await session.commit()
        await session.refresh(client)

        manager = (await session.execute(select(User).limit(1))).scalar_one()

    try:
        first = await _create_order_with_number(client.id, manager.id)
        second = await _create_order_with_number(client.id, manager.id)
        assert [first, second] == ["TST98-1", "TST98-2"]

        # Drop the first one: the client is now left holding only TST98-2.
        async with async_session_factory() as session:
            await session.execute(delete(Order).where(Order.number == first))
            await session.commit()

        assert await _create_order_with_number(client.id, manager.id) == "TST98-3"
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(Order).where(Order.client_id == client.id))
            await session.execute(delete(Client).where(Client.id == client.id))
            await session.commit()


@pytest.mark.asyncio
async def test_renaming_a_client_restarts_numbering_under_the_new_code():
    async with async_session_factory() as session:
        client = Client(code="TST97", full_name="Renamed Client")
        session.add(client)
        await session.commit()
        await session.refresh(client)

        manager = (await session.execute(select(User).limit(1))).scalar_one()

    try:
        assert await _create_order_with_number(client.id, manager.id) == "TST97-1"

        async with async_session_factory() as session:
            renamed = (await session.execute(select(Client).where(Client.id == client.id))).scalar_one()
            renamed.code = "TST96"
            await session.commit()

        assert await _create_order_with_number(client.id, manager.id) == "TST96-1"
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(Order).where(Order.client_id == client.id))
            await session.execute(delete(Client).where(Client.id == client.id))
            await session.commit()
