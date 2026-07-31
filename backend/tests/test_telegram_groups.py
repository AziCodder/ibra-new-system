import pytest
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.models.client import Client
from app.models.telegram_group import ClientTelegramGroup, TelegramGroup
from app.services.telegram_groups import get_client_send_targets


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
