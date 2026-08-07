from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.client import Client
from app.models.logistics import Logistics, LogisticsStatus
from app.models.logistics_comment import LogisticsComment
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.routers.logistics import create_logistics
from app.routers.logistics import create_logistics_comment as add_comment
from app.routers.logistics import list_logistics_comments as list_comments
from app.schemas.logistics import LogisticsCreate, LogisticsItemIn
from app.schemas.logistics_comment import LogisticsCommentCreate

SHIP_DATE = datetime.now(UTC)


async def _setup(logistics_status: LogisticsStatus = LogisticsStatus.in_transit):
    async with async_session_factory() as session:
        client = Client(code="TSTLGCM", full_name="Logistics Comments Client")
        supplier = Supplier(name="Logistics Comments Supplier")
        owner = User(login="lgcm_owner", password_hash=hash_password("x"), role=UserRole.manager, full_name="Owner Manager")
        other = User(login="lgcm_other", password_hash=hash_password("x"), role=UserRole.manager, full_name="Other Manager")
        observer = User(login="lgcm_observer", password_hash=hash_password("x"), role=UserRole.observer, full_name="Observer")
        admin = User(login="lgcm_admin", password_hash=hash_password("x"), role=UserRole.admin, full_name="Admin")
        session.add_all([client, supplier, owner, other, observer, admin])
        await session.commit()
        for obj in (client, supplier, owner, other, observer, admin):
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

        product = Product(
            order_id=order.id,
            supplier_id=supplier.id,
            name="Widget",
            quantity=Decimal("20"),
            price=Decimal("5.00"),
            currency="USD",
        )
        session.add(product)
        await session.commit()
        await session.refresh(product)

    creator = admin if logistics_status == LogisticsStatus.accepted else owner
    async with async_session_factory() as session:
        logistics = await create_logistics(
            order.id,
            LogisticsCreate(
                    items=[LogisticsItemIn(product_id=product.id, quantity=Decimal("5"))],
                    ship_date=SHIP_DATE, status=logistics_status),
            creator,
            session,
        )

    return client, supplier, owner, other, observer, admin, order, logistics


async def _cleanup(client_id: int, supplier_id: int, user_ids: list[int]):
    async with async_session_factory() as session:
        order_ids = select(Order.id).where(Order.client_id == client_id)
        logistics_ids = select(Logistics.id).where(Logistics.order_id.in_(order_ids))
        await session.execute(delete(LogisticsComment).where(LogisticsComment.logistics_id.in_(logistics_ids)))
        await session.execute(delete(Logistics).where(Logistics.order_id.in_(order_ids)))
        await session.execute(delete(Product).where(Product.order_id.in_(order_ids)))
        await session.execute(delete(Order).where(Order.client_id == client_id))
        await session.execute(delete(Client).where(Client.id == client_id))
        await session.execute(delete(Supplier).where(Supplier.id == supplier_id))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_create_comment_persists_with_author_and_date():
    client, supplier, owner, other, observer, admin, order, logistics = await _setup()
    try:
        async with async_session_factory() as session:
            created = await add_comment(order.id, logistics.id, LogisticsCommentCreate(text="first comment"), owner, session)
            assert created.text == "first comment"
            assert created.author_name == "Owner Manager"
            assert created.created_at is not None

        async with async_session_factory() as session:
            comments = await list_comments(order.id, logistics.id, owner, session)
            assert len(comments) == 1
            assert comments[0].text == "first comment"
            assert comments[0].author_id == owner.id
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_comments_listed_in_chronological_order():
    client, supplier, owner, other, observer, admin, order, logistics = await _setup()
    try:
        async with async_session_factory() as session:
            await add_comment(order.id, logistics.id, LogisticsCommentCreate(text="first"), owner, session)
        async with async_session_factory() as session:
            await add_comment(order.id, logistics.id, LogisticsCommentCreate(text="second"), owner, session)

        async with async_session_factory() as session:
            comments = await list_comments(order.id, logistics.id, owner, session)
            assert [c.text for c in comments] == ["first", "second"]
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_observer_can_add_comment():
    client, supplier, owner, other, observer, admin, order, logistics = await _setup()
    try:
        async with async_session_factory() as session:
            created = await add_comment(
                order.id, logistics.id, LogisticsCommentCreate(text="observer note"), observer, session
            )
            assert created.text == "observer note"
            assert created.author_name == "Observer"
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_comment_addable_to_accepted_logistics():
    client, supplier, owner, other, observer, admin, order, logistics = await _setup(LogisticsStatus.accepted)
    try:
        assert logistics.status == LogisticsStatus.accepted
        async with async_session_factory() as session:
            created = await add_comment(
                order.id, logistics.id, LogisticsCommentCreate(text="comment on accepted"), owner, session
            )
            assert created.text == "comment on accepted"
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_comment_addable_to_cancelled_logistics():
    client, supplier, owner, other, observer, admin, order, logistics = await _setup(LogisticsStatus.cancelled)
    try:
        assert logistics.status == LogisticsStatus.cancelled
        async with async_session_factory() as session:
            created = await add_comment(
                order.id, logistics.id, LogisticsCommentCreate(text="comment on cancelled"), admin, session
            )
            assert created.text == "comment on cancelled"
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])


@pytest.mark.asyncio
async def test_manager_cannot_view_or_add_comments_on_other_managers_order():
    client, supplier, owner, other, observer, admin, order, logistics = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await list_comments(order.id, logistics.id, other, session)
            assert exc_info.value.status_code == 404

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await add_comment(order.id, logistics.id, LogisticsCommentCreate(text="should fail"), other, session)
            assert exc_info.value.status_code == 404
    finally:
        await _cleanup(client.id, supplier.id, [owner.id, other.id, observer.id, admin.id])
