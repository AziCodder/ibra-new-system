import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.models.client import Client
from app.models.telegram_group import ClientTelegramGroup, TelegramGroup
from app.models.user import User, UserRole
from app.routers.telegram_groups import (
    delete_telegram_group,
    list_telegram_groups,
    set_telegram_group_clients,
)
from app.schemas.telegram_group import TelegramGroupClientsIn
from app.services.telegram_groups import get_client_send_targets


async def _admin_user() -> User:
    async with async_session_factory() as session:
        return (
            await session.execute(select(User).where(User.role == UserRole.admin).limit(1))
        ).scalar_one()


@pytest.mark.asyncio
async def test_get_client_send_targets_empty_for_unlinked_client():
    async with async_session_factory() as session:
        client = Client(code="TSTGST1", full_name="Unlinked Client", telegram_chat_id="900001")
        session.add(client)
        await session.commit()
        await session.refresh(client)
        client_id = client.id

    try:
        async with async_session_factory() as session:
            client_obj = (await session.execute(select(Client).where(Client.id == client_id))).scalar_one()
            targets = await get_client_send_targets(client_obj, session)
            assert targets == []
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(Client).where(Client.id == client_id))
            await session.commit()


@pytest.mark.asyncio
async def test_get_client_send_targets_returns_groups_sorted_by_title():
    async with async_session_factory() as session:
        client = Client(code="TSTGST2", full_name="Multi Group Client", telegram_chat_id="900002")
        group_b = TelegramGroup(chat_id="-100777888", title="Bravo Group")
        group_a = TelegramGroup(chat_id="-100888999", title="Alpha Group")
        session.add_all([client, group_b, group_a])
        await session.commit()
        for obj in (client, group_b, group_a):
            await session.refresh(obj)
        client_id, group_b_id, group_a_id = client.id, group_b.id, group_a.id

        session.add(ClientTelegramGroup(client_id=client_id, group_id=group_b_id))
        session.add(ClientTelegramGroup(client_id=client_id, group_id=group_a_id))
        await session.commit()

    try:
        async with async_session_factory() as session:
            client_obj = (await session.execute(select(Client).where(Client.id == client_id))).scalar_one()
            targets = await get_client_send_targets(client_obj, session)
            assert [t["title"] for t in targets] == ["Alpha Group", "Bravo Group"]
            assert {t["group_id"] for t in targets} == {group_a_id, group_b_id}
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(ClientTelegramGroup).where(ClientTelegramGroup.client_id == client_id))
            await session.execute(delete(Client).where(Client.id == client_id))
            await session.execute(delete(TelegramGroup).where(TelegramGroup.id.in_([group_a_id, group_b_id])))
            await session.commit()


@pytest.mark.asyncio
async def test_get_client_send_targets_skips_chats_the_bot_was_removed_from():
    """An inactive chat keeps its link but must never be offered as a target."""
    async with async_session_factory() as session:
        client = Client(code="TSTGST3", full_name="Kicked Group Client", telegram_chat_id="900003")
        live = TelegramGroup(chat_id="-100111000", title="Live Group")
        kicked = TelegramGroup(chat_id="-100222000", title="Kicked Group", is_active=False)
        session.add_all([client, live, kicked])
        await session.commit()
        for obj in (client, live, kicked):
            await session.refresh(obj)
        client_id, live_id, kicked_id = client.id, live.id, kicked.id

        session.add_all([
            ClientTelegramGroup(client_id=client_id, group_id=live_id),
            ClientTelegramGroup(client_id=client_id, group_id=kicked_id),
        ])
        await session.commit()

    try:
        async with async_session_factory() as session:
            client_obj = (await session.execute(select(Client).where(Client.id == client_id))).scalar_one()
            targets = await get_client_send_targets(client_obj, session)
            assert [t["group_id"] for t in targets] == [live_id]
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(ClientTelegramGroup).where(ClientTelegramGroup.client_id == client_id))
            await session.execute(delete(Client).where(Client.id == client_id))
            await session.execute(delete(TelegramGroup).where(TelegramGroup.id.in_([live_id, kicked_id])))
            await session.commit()


@pytest.mark.asyncio
async def test_admin_sets_the_exact_client_list_of_a_chat():
    """The chat serves whoever the admin ticked — one call replaces the whole list."""
    admin = await _admin_user()
    async with async_session_factory() as session:
        first = Client(code="TSTTGA1", full_name="First Client")
        second = Client(code="TSTTGA2", full_name="Second Client")
        group = TelegramGroup(chat_id="-100333000", title="Shared Group")
        session.add_all([first, second, group])
        await session.commit()
        for obj in (first, second, group):
            await session.refresh(obj)
        first_id, second_id, group_id = first.id, second.id, group.id

    try:
        async with async_session_factory() as session:
            out = await set_telegram_group_clients(
                group_id=group_id,
                body=TelegramGroupClientsIn(client_ids=[first_id, second_id]),
                _admin=admin,
                session=session,
            )
            assert out.client_ids == sorted([first_id, second_id])

        # Both clients now send into the same chat — that is the point of the many-to-many.
        async with async_session_factory() as session:
            for client_id in (first_id, second_id):
                client_obj = (await session.execute(select(Client).where(Client.id == client_id))).scalar_one()
                assert [t["group_id"] for t in await get_client_send_targets(client_obj, session)] == [group_id]

        async with async_session_factory() as session:
            out = await set_telegram_group_clients(
                group_id=group_id,
                body=TelegramGroupClientsIn(client_ids=[second_id]),
                _admin=admin,
                session=session,
            )
            assert out.client_ids == [second_id]

        async with async_session_factory() as session:
            dropped = (await session.execute(select(Client).where(Client.id == first_id))).scalar_one()
            assert await get_client_send_targets(dropped, session) == []
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(ClientTelegramGroup).where(ClientTelegramGroup.group_id == group_id))
            await session.execute(delete(Client).where(Client.id.in_([first_id, second_id])))
            await session.execute(delete(TelegramGroup).where(TelegramGroup.id == group_id))
            await session.commit()


@pytest.mark.asyncio
async def test_linking_an_unknown_client_is_rejected():
    async with async_session_factory() as session:
        group = TelegramGroup(chat_id="-100444000", title="Validation Group")
        session.add(group)
        await session.commit()
        await session.refresh(group)
        group_id = group.id

    admin = await _admin_user()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await set_telegram_group_clients(
                    group_id=group_id,
                    body=TelegramGroupClientsIn(client_ids=[999999]),
                    _admin=admin,
                    session=session,
                )
            assert exc_info.value.status_code == 422
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(TelegramGroup).where(TelegramGroup.id == group_id))
            await session.commit()


@pytest.mark.asyncio
async def test_listing_shows_registered_chats_and_deleting_forgets_them():
    admin = await _admin_user()
    async with async_session_factory() as session:
        client = Client(code="TSTTGA3", full_name="Listed Client")
        group = TelegramGroup(chat_id="-100555000", title="Listed Group")
        session.add_all([client, group])
        await session.commit()
        for obj in (client, group):
            await session.refresh(obj)
        client_id, group_id = client.id, group.id
        session.add(ClientTelegramGroup(client_id=client_id, group_id=group_id))
        await session.commit()

    try:
        async with async_session_factory() as session:
            listed = await list_telegram_groups(_admin=admin, session=session)
            mine = next(g for g in listed if g.id == group_id)
            assert mine.chat_id == "-100555000"
            assert mine.is_active is True
            assert mine.client_ids == [client_id]

        async with async_session_factory() as session:
            await delete_telegram_group(group_id=group_id, _admin=admin, session=session)

        async with async_session_factory() as session:
            listed = await list_telegram_groups(_admin=admin, session=session)
            assert all(g.id != group_id for g in listed)
            links = (
                await session.execute(
                    select(ClientTelegramGroup).where(ClientTelegramGroup.group_id == group_id)
                )
            ).scalars().all()
            assert links == []
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(ClientTelegramGroup).where(ClientTelegramGroup.client_id == client_id))
            await session.execute(delete(Client).where(Client.id == client_id))
            await session.execute(delete(TelegramGroup).where(TelegramGroup.id == group_id))
            await session.commit()
