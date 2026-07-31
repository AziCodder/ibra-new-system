import pytest
from fastapi import HTTPException
from sqlalchemy import delete

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.client import Client
from app.models.order import Order
from app.models.order_sort_position import OrderSortPosition
from app.models.user import User, UserRole
from app.routers.orders import list_orders, reorder_orders
from app.schemas.order import OrderReorderIn


async def _setup(order_count: int = 3):
    """Клиент, два админа, два менеджера и order_count заказов первого менеджера."""
    async with async_session_factory() as session:
        client = Client(code="TSTMS", full_name="Manual Sort Client")
        admin = User(login="ms_admin", password_hash=hash_password("x"), role=UserRole.admin, full_name="Admin One")
        admin2 = User(login="ms_admin2", password_hash=hash_password("x"), role=UserRole.admin, full_name="Admin Two")
        owner = User(login="ms_owner", password_hash=hash_password("x"), role=UserRole.manager, full_name="Owner")
        other = User(login="ms_other", password_hash=hash_password("x"), role=UserRole.manager, full_name="Other")
        session.add_all([client, admin, admin2, owner, other])
        await session.commit()
        for obj in (client, admin, admin2, owner, other):
            await session.refresh(obj)

        orders = [
            Order(number=f"MS-{index}", client_id=client.id, manager_id=owner.id)
            for index in range(order_count)
        ]
        session.add_all(orders)
        await session.commit()
        for order in orders:
            await session.refresh(order)

        return client, admin, admin2, owner, other, orders


async def _cleanup(client_id: int, user_ids: list[int]):
    async with async_session_factory() as session:
        await session.execute(delete(OrderSortPosition).where(OrderSortPosition.user_id.in_(user_ids)))
        await session.execute(delete(Order).where(Order.client_id == client_id))
        await session.execute(delete(Client).where(Client.id == client_id))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


async def _manual_ids(client_id: int, user: User, page: int = 1, page_size: int = 50) -> list[int]:
    async with async_session_factory() as session:
        listing = await list_orders(
            client_id=client_id,
            status=None,
            manager_id=None,
            search=None,
            sort_by="manual",
            sort_order="asc",
            page=page,
            page_size=page_size,
            user=user,
            session=session,
        )
        return [item.id for item in listing.items]


@pytest.mark.asyncio
async def test_manual_sort_returns_saved_order():
    client, admin, admin2, owner, other, orders = await _setup()
    user_ids = [admin.id, admin2.id, owner.id, other.id]
    try:
        first, second, third = orders
        # По умолчанию — новые сверху.
        assert await _manual_ids(client.id, admin) == [third.id, second.id, first.id]

        wanted = [second.id, first.id, third.id]
        async with async_session_factory() as session:
            await reorder_orders(OrderReorderIn(order_ids=wanted), admin, session)

        assert await _manual_ids(client.id, admin) == wanted
    finally:
        await _cleanup(client.id, user_ids)


@pytest.mark.asyncio
async def test_manual_order_is_personal():
    client, admin, admin2, owner, other, orders = await _setup()
    user_ids = [admin.id, admin2.id, owner.id, other.id]
    try:
        first, second, third = orders
        async with async_session_factory() as session:
            await reorder_orders(OrderReorderIn(order_ids=[first.id, second.id, third.id]), admin, session)

        # У другого пользователя порядок не поменялся.
        assert await _manual_ids(client.id, admin2) == [third.id, second.id, first.id]
    finally:
        await _cleanup(client.id, user_ids)


@pytest.mark.asyncio
async def test_new_order_appears_first_in_manual_mode():
    client, admin, admin2, owner, other, orders = await _setup()
    user_ids = [admin.id, admin2.id, owner.id, other.id]
    try:
        first, second, third = orders
        async with async_session_factory() as session:
            await reorder_orders(OrderReorderIn(order_ids=[first.id, second.id, third.id]), admin, session)

        async with async_session_factory() as session:
            fresh = Order(number="MS-fresh", client_id=client.id, manager_id=owner.id)
            session.add(fresh)
            await session.commit()
            await session.refresh(fresh)

        # Заказ, созданный после перестановки, не теряется в конце списка.
        assert await _manual_ids(client.id, admin) == [fresh.id, first.id, second.id, third.id]
    finally:
        await _cleanup(client.id, user_ids)


@pytest.mark.asyncio
async def test_reorder_inside_page_keeps_other_pages_untouched():
    client, admin, admin2, owner, other, orders = await _setup(order_count=4)
    user_ids = [admin.id, admin2.id, owner.id, other.id]
    try:
        first, second, third, fourth = orders
        # Страница 2 при page_size=2 — два самых старых заказа.
        assert await _manual_ids(client.id, admin, page=2, page_size=2) == [second.id, first.id]

        async with async_session_factory() as session:
            await reorder_orders(OrderReorderIn(order_ids=[first.id, second.id]), admin, session)

        assert await _manual_ids(client.id, admin, page=1, page_size=2) == [fourth.id, third.id]
        assert await _manual_ids(client.id, admin, page=2, page_size=2) == [first.id, second.id]
    finally:
        await _cleanup(client.id, user_ids)


@pytest.mark.asyncio
async def test_manager_cannot_reorder_someone_elses_orders():
    client, admin, admin2, owner, other, orders = await _setup()
    user_ids = [admin.id, admin2.id, owner.id, other.id]
    try:
        first, second, third = orders
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await reorder_orders(OrderReorderIn(order_ids=[first.id, second.id, third.id]), other, session)
            assert exc_info.value.status_code == 404

        # Свои заказы менеджер переставляет свободно.
        async with async_session_factory() as session:
            await reorder_orders(OrderReorderIn(order_ids=[second.id, third.id, first.id]), owner, session)
        assert await _manual_ids(client.id, owner) == [second.id, third.id, first.id]
    finally:
        await _cleanup(client.id, user_ids)


@pytest.mark.asyncio
async def test_reorder_rejects_duplicate_ids():
    client, admin, admin2, owner, other, orders = await _setup()
    user_ids = [admin.id, admin2.id, owner.id, other.id]
    try:
        first = orders[0]
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await reorder_orders(OrderReorderIn(order_ids=[first.id, first.id]), admin, session)
            assert exc_info.value.status_code == 422
    finally:
        await _cleanup(client.id, user_ids)
