import pytest
from fastapi import HTTPException
from sqlalchemy import delete

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.action_log import ActionLog
from app.models.client import Client
from app.models.order import Order
from app.models.user import User, UserRole
from app.routers.orders import add_order_file, create_order, get_order, remove_order_file, update_order
from app.schemas.order import MAX_ORDER_FILES, OrderCreate, OrderFileAdd, OrderUpdate


async def _setup():
    async with async_session_factory() as session:
        client = Client(code="TSTORD", full_name="Orders Test Client")
        admin = User(login="ord_admin", password_hash=hash_password("x"), role=UserRole.admin, full_name="Admin")
        owner = User(login="ord_owner", password_hash=hash_password("x"), role=UserRole.manager, full_name="Owner Manager")
        other = User(login="ord_other", password_hash=hash_password("x"), role=UserRole.manager, full_name="Other Manager")
        observer = User(login="ord_observer", password_hash=hash_password("x"), role=UserRole.observer, full_name="Observer")
        session.add_all([client, admin, owner, other, observer])
        await session.commit()
        for obj in (client, admin, owner, other, observer):
            await session.refresh(obj)
        return client, admin, owner, other, observer


async def _cleanup(client_id: int, user_ids: list[int]):
    async with async_session_factory() as session:
        await session.execute(delete(Order).where(Order.client_id == client_id))
        await session.execute(delete(Client).where(Client.id == client_id))
        await session.execute(delete(ActionLog).where(ActionLog.actor_id.in_(user_ids)))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_admin_can_create_order_for_another_manager():
    client, admin, owner, other, observer = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_order(
                OrderCreate(client_id=client.id, manager_id=owner.id), admin, session
            )
            assert created.manager_id == owner.id
            assert created.manager_name == "Owner Manager"
    finally:
        await _cleanup(client.id, [admin.id, owner.id, other.id, observer.id])


@pytest.mark.asyncio
async def test_manager_cannot_assign_a_different_manager_at_creation():
    client, admin, owner, other, observer = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_order(OrderCreate(client_id=client.id, manager_id=other.id), owner, session)
            assert exc_info.value.status_code == 403
    finally:
        await _cleanup(client.id, [admin.id, owner.id, other.id, observer.id])


@pytest.mark.asyncio
async def test_create_order_rejects_nonexistent_manager_id():
    client, admin, owner, other, observer = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_order(OrderCreate(client_id=client.id, manager_id=999999), admin, session)
            assert exc_info.value.status_code == 404
    finally:
        await _cleanup(client.id, [admin.id, owner.id, other.id, observer.id])


@pytest.mark.asyncio
async def test_create_order_rejects_observer_as_manager():
    client, admin, owner, other, observer = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_order(OrderCreate(client_id=client.id, manager_id=observer.id), admin, session)
            assert exc_info.value.status_code == 422
    finally:
        await _cleanup(client.id, [admin.id, owner.id, other.id, observer.id])


@pytest.mark.asyncio
async def test_admin_can_reassign_order_manager_and_access_transfers():
    client, admin, owner, other, observer = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_order(OrderCreate(client_id=client.id), owner, session)

        async with async_session_factory() as session:
            updated = await update_order(created.id, OrderUpdate(details="", manager_id=other.id), admin, session)
            assert updated.manager_id == other.id
            assert updated.manager_name == "Other Manager"

        # Old manager loses access.
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await get_order(created.id, owner, session)
            assert exc_info.value.status_code == 404

        # New manager has access.
        async with async_session_factory() as session:
            fetched = await get_order(created.id, other, session)
            assert fetched.manager_id == other.id
    finally:
        await _cleanup(client.id, [admin.id, owner.id, other.id, observer.id])


@pytest.mark.asyncio
async def test_create_order_with_file_keys():
    client, admin, owner, other, observer = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_order(
                OrderCreate(client_id=client.id, file_keys=["a.pdf", "b.pdf"]), owner, session
            )
            assert created.file_keys == ["a.pdf", "b.pdf"]
    finally:
        await _cleanup(client.id, [admin.id, owner.id, other.id, observer.id])


@pytest.mark.asyncio
async def test_add_and_remove_order_file():
    client, admin, owner, other, observer = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_order(OrderCreate(client_id=client.id), owner, session)

        async with async_session_factory() as session:
            added = await add_order_file(created.id, OrderFileAdd(file_key="invoice.pdf"), owner, session)
            assert added.file_keys == ["invoice.pdf"]

        async with async_session_factory() as session:
            removed = await remove_order_file(created.id, "invoice.pdf", owner, session)
            assert removed.file_keys == []
    finally:
        await _cleanup(client.id, [admin.id, owner.id, other.id, observer.id])


@pytest.mark.asyncio
async def test_order_file_cap_enforced():
    client, admin, owner, other, observer = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_order(OrderCreate(client_id=client.id), owner, session)

        for i in range(MAX_ORDER_FILES):
            async with async_session_factory() as session:
                await add_order_file(created.id, OrderFileAdd(file_key=f"file{i}.pdf"), owner, session)

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await add_order_file(created.id, OrderFileAdd(file_key="one_too_many.pdf"), owner, session)
            assert exc_info.value.status_code == 422
    finally:
        await _cleanup(client.id, [admin.id, owner.id, other.id, observer.id])


@pytest.mark.asyncio
async def test_observer_cannot_add_order_file():
    client, admin, owner, other, observer = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_order(OrderCreate(client_id=client.id), owner, session)

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await add_order_file(created.id, OrderFileAdd(file_key="invoice.pdf"), observer, session)
            assert exc_info.value.status_code == 403
    finally:
        await _cleanup(client.id, [admin.id, owner.id, other.id, observer.id])


@pytest.mark.asyncio
async def test_other_manager_cannot_add_file_to_owners_order():
    client, admin, owner, other, observer = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_order(OrderCreate(client_id=client.id), owner, session)

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await add_order_file(created.id, OrderFileAdd(file_key="invoice.pdf"), other, session)
            assert exc_info.value.status_code == 404
    finally:
        await _cleanup(client.id, [admin.id, owner.id, other.id, observer.id])
