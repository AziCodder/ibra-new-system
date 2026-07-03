import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.client import Client
from app.models.note import Note
from app.models.order import Order, OrderStatus
from app.models.user import User, UserRole
from app.routers.notes import create_note, list_notes
from app.schemas.note import NoteCreate


async def _setup_order_with_managers():
    async with async_session_factory() as session:
        client = Client(code="TSTNT", full_name="Notes Test Client")
        session.add(client)

        owner = User(login="notes_owner", password_hash=hash_password("x"), role=UserRole.manager, full_name="Owner Manager")
        other = User(login="notes_other", password_hash=hash_password("x"), role=UserRole.manager, full_name="Other Manager")
        session.add_all([owner, other])
        await session.commit()
        await session.refresh(client)
        await session.refresh(owner)
        await session.refresh(other)

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
        return client, owner, other, order


async def _cleanup(client_id: int, user_ids: list[int]):
    async with async_session_factory() as session:
        await session.execute(delete(Note).where(Note.order_id.in_(select(Order.id).where(Order.client_id == client_id))))
        await session.execute(delete(Order).where(Order.client_id == client_id))
        await session.execute(delete(Client).where(Client.id == client_id))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_create_note_persists_with_author_and_date():
    client, owner, other, order = await _setup_order_with_managers()
    try:
        async with async_session_factory() as session:
            created = await create_note(order.id, NoteCreate(text="first note"), owner, session)
            assert created.text == "first note"
            assert created.author_name == "Owner Manager"
            assert created.created_at is not None

        async with async_session_factory() as session:
            notes = await list_notes(order.id, owner, session)
            assert len(notes) == 1
            assert notes[0].text == "first note"
            assert notes[0].author_id == owner.id
    finally:
        await _cleanup(client.id, [owner.id, other.id])


@pytest.mark.asyncio
async def test_notes_listed_in_chronological_order():
    client, owner, other, order = await _setup_order_with_managers()
    try:
        async with async_session_factory() as session:
            await create_note(order.id, NoteCreate(text="first"), owner, session)
        async with async_session_factory() as session:
            await create_note(order.id, NoteCreate(text="second"), owner, session)

        async with async_session_factory() as session:
            notes = await list_notes(order.id, owner, session)
            assert [n.text for n in notes] == ["first", "second"]
    finally:
        await _cleanup(client.id, [owner.id, other.id])


@pytest.mark.asyncio
async def test_manager_cannot_view_or_add_notes_on_other_managers_order():
    client, owner, other, order = await _setup_order_with_managers()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await list_notes(order.id, other, session)
            assert exc_info.value.status_code == 404

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_note(order.id, NoteCreate(text="should fail"), other, session)
            assert exc_info.value.status_code == 404
    finally:
        await _cleanup(client.id, [owner.id, other.id])


@pytest.mark.asyncio
async def test_observer_can_read_but_cannot_create_notes():
    client, owner, other, order = await _setup_order_with_managers()
    try:
        async with async_session_factory() as session:
            observer = User(login="notes_observer", password_hash=hash_password("x"), role=UserRole.observer, full_name="Observer")
            session.add(observer)
            await session.commit()
            await session.refresh(observer)
            observer_id = observer.id

        async with async_session_factory() as session:
            await create_note(order.id, NoteCreate(text="existing"), owner, session)

        async with async_session_factory() as session:
            observer = await session.get(User, observer_id)
            notes = await list_notes(order.id, observer, session)
            assert len(notes) == 1
            assert notes[0].text == "existing"

        async with async_session_factory() as session:
            observer = await session.get(User, observer_id)
            with pytest.raises(HTTPException) as exc_info:
                await create_note(order.id, NoteCreate(text="blocked"), observer, session)
            assert exc_info.value.status_code == 403
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(User).where(User.login == "notes_observer"))
            await session.commit()
        await _cleanup(client.id, [owner.id, other.id])
