import pytest
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.models.client import Client
from app.models.order import Order, OrderStatus
from app.models.user import User, UserRole
from app.services.order_dependencies import count_order_dependencies


async def _setup_order():
    async with async_session_factory() as session:
        client = Client(code="TSTED", full_name="Edit/Delete Test Client")
        session.add(client)
        await session.commit()
        await session.refresh(client)

        manager_result = await session.execute(select(User).where(User.role == UserRole.admin).limit(1))
        manager = manager_result.scalar_one()

        order = Order(
            number=f"{client.code}-1",
            client_id=client.id,
            manager_id=manager.id,
            status=OrderStatus.in_progress,
            currency="USD",
            details="original details",
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)
        return client, order


async def _cleanup(client_id: int):
    async with async_session_factory() as session:
        await session.execute(delete(Order).where(Order.client_id == client_id))
        await session.execute(delete(Client).where(Client.id == client_id))
        await session.commit()


@pytest.mark.asyncio
async def test_count_order_dependencies_is_zero_with_no_related_entities():
    client, order = await _setup_order()
    try:
        async with async_session_factory() as session:
            count = await count_order_dependencies(session, order.id)
            assert count == 0
    finally:
        await _cleanup(client.id)


@pytest.mark.asyncio
async def test_update_order_details_persists():
    client, order = await _setup_order()
    try:
        async with async_session_factory() as session:
            result = await session.execute(select(Order).where(Order.id == order.id))
            fetched = result.scalar_one()
            fetched.details = "updated details"
            await session.commit()

        async with async_session_factory() as session:
            result = await session.execute(select(Order).where(Order.id == order.id))
            reread = result.scalar_one()
            assert reread.details == "updated details"
    finally:
        await _cleanup(client.id)


@pytest.mark.asyncio
async def test_delete_order_with_no_dependencies_removes_row():
    client, order = await _setup_order()
    try:
        async with async_session_factory() as session:
            dependency_count = await count_order_dependencies(session, order.id)
            assert dependency_count == 0

            result = await session.execute(select(Order).where(Order.id == order.id))
            to_delete = result.scalar_one()
            await session.delete(to_delete)
            await session.commit()

        async with async_session_factory() as session:
            result = await session.execute(select(Order).where(Order.id == order.id))
            assert result.scalar_one_or_none() is None
    finally:
        await _cleanup(client.id)
