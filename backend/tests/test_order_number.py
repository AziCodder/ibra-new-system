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
