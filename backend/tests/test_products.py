from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.action_log import ActionLog
from app.models.client import Client
from app.models.logistics import Logistics
from app.models.order import Order, OrderStatus
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest, PaymentRequestItem
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.routers.logistics import accept_logistics, create_logistics, update_logistics
from app.routers.payment_requests import create_payment_request
from app.routers.payments import create_payment
from app.routers.products import create_product, delete_product, list_products, update_product
from app.schemas.logistics import LogisticsAccept, LogisticsCreate, LogisticsItemIn, LogisticsUpdate
from app.schemas.payment import PaymentCreate
from app.schemas.payment_request import PaymentRequestCreate, PaymentRequestItemIn
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.product_dependencies import count_product_dependencies


async def _setup():
    async with async_session_factory() as session:
        client = Client(code="TSTPR", full_name="Products Test Client")
        session.add(client)

        owner = User(login="prod_owner", password_hash=hash_password("x"), role=UserRole.manager, full_name="Owner Manager")
        other = User(login="prod_other", password_hash=hash_password("x"), role=UserRole.manager, full_name="Other Manager")
        observer = User(login="prod_observer", password_hash=hash_password("x"), role=UserRole.observer, full_name="Observer")
        supplier = Supplier(name="Products Test Supplier")
        session.add_all([owner, other, observer, supplier])
        await session.commit()
        for obj in (client, owner, other, observer, supplier):
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
        return client, owner, other, observer, supplier, order


async def _cleanup(client_id: int, user_ids: list[int], supplier_id: int):
    async with async_session_factory() as session:
        order_ids = select(Order.id).where(Order.client_id == client_id)
        request_ids = select(PaymentRequest.id).where(PaymentRequest.order_id.in_(order_ids))
        await session.execute(delete(Payment).where(Payment.payment_request_id.in_(request_ids)))
        await session.execute(delete(PaymentRequestItem).where(PaymentRequestItem.payment_request_id.in_(request_ids)))
        await session.execute(delete(PaymentRequest).where(PaymentRequest.order_id.in_(order_ids)))
        await session.execute(delete(Logistics).where(Logistics.order_id.in_(order_ids)))
        await session.execute(
            delete(Product).where(Product.order_id.in_(select(Order.id).where(Order.client_id == client_id)))
        )
        await session.execute(delete(Order).where(Order.client_id == client_id))
        await session.execute(delete(Client).where(Client.id == client_id))
        # action_logs reference users (FK) — accepting a shipment writes one.
        await session.execute(delete(ActionLog).where(ActionLog.actor_id.in_(user_ids)))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.execute(delete(Supplier).where(Supplier.id == supplier_id))
        await session.commit()


@pytest.mark.asyncio
async def test_create_update_delete_product_lifecycle():
    client, owner, other, observer, supplier, order = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_product(
                order.id,
                ProductCreate(supplier_id=supplier.id, name="Widget", quantity=Decimal("3"), price=Decimal("12.50")),
                owner,
                session,
            )
            assert created.name == "Widget"
            assert created.quantity == Decimal("3")
            assert created.supplier_name == "Products Test Supplier"

        async with async_session_factory() as session:
            updated = await update_product(
                order.id, created.id, ProductUpdate(price=Decimal("15.00"), quantity=Decimal("5")), owner, session
            )
            assert updated.price == Decimal("15.00")
            assert updated.quantity == Decimal("5")
            assert updated.name == "Widget"

        async with async_session_factory() as session:
            await delete_product(order.id, created.id, owner, session)

        async with async_session_factory() as session:
            products = await list_products(order.id, owner, session)
            assert products == []
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id], supplier.id)


@pytest.mark.asyncio
async def test_count_product_dependencies_is_zero_with_no_related_entities():
    client, owner, other, observer, supplier, order = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_product(
                order.id,
                ProductCreate(supplier_id=supplier.id, name="Widget", quantity=Decimal("1"), price=Decimal("1")),
                owner,
                session,
            )

        async with async_session_factory() as session:
            count = await count_product_dependencies(session, created.id)
            assert count == 0

        async with async_session_factory() as session:
            await delete_product(order.id, created.id, owner, session)

        async with async_session_factory() as session:
            products = await list_products(order.id, owner, session)
            assert products == []
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id], supplier.id)


@pytest.mark.asyncio
async def test_manager_cannot_crud_products_on_other_managers_order():
    client, owner, other, observer, supplier, order = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await list_products(order.id, other, session)
            assert exc_info.value.status_code == 404

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_product(
                    order.id,
                    ProductCreate(supplier_id=supplier.id, name="Widget", quantity=Decimal("1"), price=Decimal("1")),
                    other,
                    session,
                )
            assert exc_info.value.status_code == 404
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id], supplier.id)


@pytest.mark.asyncio
async def test_observer_can_read_but_not_write_products():
    client, owner, other, observer, supplier, order = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_product(
                order.id,
                ProductCreate(supplier_id=supplier.id, name="Widget", quantity=Decimal("1"), price=Decimal("1")),
                owner,
                session,
            )

        async with async_session_factory() as session:
            products = await list_products(order.id, observer, session)
            assert len(products) == 1

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_product(
                    order.id,
                    ProductCreate(supplier_id=supplier.id, name="Gadget", quantity=Decimal("1"), price=Decimal("1")),
                    observer,
                    session,
                )
            assert exc_info.value.status_code == 403

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await update_product(order.id, created.id, ProductUpdate(name="Changed"), observer, session)
            assert exc_info.value.status_code == 403

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await delete_product(order.id, created.id, observer, session)
            assert exc_info.value.status_code == 403
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id], supplier.id)


@pytest.mark.asyncio
async def test_cannot_lower_quantity_below_already_shipped():
    client, owner, other, observer, supplier, order = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_product(
                order.id,
                ProductCreate(supplier_id=supplier.id, name="Widget", quantity=Decimal("10"), price=Decimal("5.00")),
                owner,
                session,
            )

        async with async_session_factory() as session:
            await create_logistics(
                order.id,
                LogisticsCreate(
                    items=[LogisticsItemIn(product_id=created.id, quantity=Decimal("6"))],
                    ship_date=datetime.now(UTC)),
                owner,
                session,
            )

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await update_product(order.id, created.id, ProductUpdate(quantity=Decimal("5")), owner, session)
            assert exc_info.value.status_code == 422

        # Still allowed to lower down to (but not below) the already-shipped amount.
        async with async_session_factory() as session:
            updated = await update_product(order.id, created.id, ProductUpdate(quantity=Decimal("6")), owner, session)
            assert updated.quantity == Decimal("6")
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id], supplier.id)


@pytest.mark.asyncio
async def test_cannot_lower_total_value_below_already_requested():
    client, owner, other, observer, supplier, order = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_product(
                order.id,
                ProductCreate(supplier_id=supplier.id, name="Widget", quantity=Decimal("10"), price=Decimal("5.00")),
                owner,
                session,
            )

        async with async_session_factory() as session:
            await create_payment_request(
                order.id,
                PaymentRequestCreate(items=[PaymentRequestItemIn(product_id=created.id, amount=Decimal("30.00"))]),
                owner,
                session,
            )

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await update_product(order.id, created.id, ProductUpdate(price=Decimal("2.00")), owner, session)
            assert exc_info.value.status_code == 422
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id], supplier.id)


@pytest.mark.asyncio
async def test_cannot_change_currency_with_existing_payment_request():
    client, owner, other, observer, supplier, order = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_product(
                order.id,
                ProductCreate(supplier_id=supplier.id, name="Widget", quantity=Decimal("10"), price=Decimal("5.00")),
                owner,
                session,
            )

        async with async_session_factory() as session:
            await create_payment_request(
                order.id,
                PaymentRequestCreate(items=[PaymentRequestItemIn(product_id=created.id, amount=Decimal("10.00"))]),
                owner,
                session,
            )

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await update_product(order.id, created.id, ProductUpdate(currency="CNY"), owner, session)
            assert exc_info.value.status_code == 422
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id], supplier.id)


@pytest.mark.asyncio
async def test_create_product_defaults_currency_to_order_currency():
    client, owner, other, observer, supplier, order = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_product(
                order.id,
                ProductCreate(supplier_id=supplier.id, name="Widget", quantity=Decimal("1"), price=Decimal("1")),
                owner,
                session,
            )
            assert created.currency == order.currency == "USD"
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id], supplier.id)


@pytest.mark.asyncio
async def test_create_product_rejects_currency_mismatch():
    client, owner, other, observer, supplier, order = await _setup()
    try:
        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_product(
                    order.id,
                    ProductCreate(
                        supplier_id=supplier.id, name="Widget", quantity=Decimal("1"), price=Decimal("1"),
                        currency="CNY",
                    ),
                    owner,
                    session,
                )
            assert exc_info.value.status_code == 422
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id], supplier.id)


@pytest.mark.asyncio
async def test_update_product_to_foreign_currency_requires_an_exchange_rate():
    client, owner, other, observer, supplier, order = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_product(
                order.id,
                ProductCreate(supplier_id=supplier.id, name="Widget", quantity=Decimal("1"), price=Decimal("1")),
                owner,
                session,
            )
            assert created.currency == "USD"
            assert created.exchange_rate == Decimal("1")

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await update_product(order.id, created.id, ProductUpdate(currency="CNY"), owner, session)
            assert exc_info.value.status_code == 422
            assert "Exchange rate is required" in exc_info.value.detail

        async with async_session_factory() as session:
            updated = await update_product(
                order.id,
                created.id,
                ProductUpdate(currency="CNY", exchange_rate=Decimal("7.2")),
                owner,
                session,
            )
            assert updated.currency == "CNY"
            assert updated.exchange_rate == Decimal("7.200000")

        async with async_session_factory() as session:
            # Switching back to the order's currency drops the now-meaningless rate.
            back = await update_product(order.id, created.id, ProductUpdate(currency="USD"), owner, session)
            assert back.exchange_rate == Decimal("1")
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id], supplier.id)


@pytest.mark.asyncio
async def test_create_product_in_a_currency_other_than_the_orders():
    client, owner, other, observer, supplier, order = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_product(
                order.id,
                ProductCreate(
                    supplier_id=supplier.id,
                    name="Imported widget",
                    quantity=Decimal("10"),
                    price=Decimal("850"),
                    currency="CNY",
                    exchange_rate=Decimal("7.2185"),
                ),
                owner,
                session,
            )
            assert created.currency == "CNY"
            assert created.exchange_rate == Decimal("7.218500")

        async with async_session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_product(
                    order.id,
                    ProductCreate(
                        supplier_id=supplier.id, name="No rate", quantity=Decimal("1"), price=Decimal("1"),
                        currency="RUB",
                    ),
                    owner,
                    session,
                )
            assert exc_info.value.status_code == 422

        async with async_session_factory() as session:
            # A rate other than 1 makes no sense in the order's own currency.
            with pytest.raises(HTTPException) as exc_info:
                await create_product(
                    order.id,
                    ProductCreate(
                        supplier_id=supplier.id, name="Bogus rate", quantity=Decimal("1"), price=Decimal("1"),
                        currency="USD", exchange_rate=Decimal("2"),
                    ),
                    owner,
                    session,
                )
            assert exc_info.value.status_code == 422
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id], supplier.id)


def test_huge_quantity_rejected_at_schema_level_not_as_a_500():
    with pytest.raises(ValidationError):
        ProductCreate(supplier_id=1, name="Widget", quantity=Decimal("99999999999999"), price=Decimal("1"))


def test_huge_price_rejected_at_schema_level_not_as_a_500():
    with pytest.raises(ValidationError):
        ProductCreate(supplier_id=1, name="Widget", quantity=Decimal("1"), price=Decimal("999999999999999"))


@pytest.mark.asyncio
async def test_product_shows_no_payment_totals_until_a_request_exists():
    client, owner, other, observer, supplier, order = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_product(
                order.id,
                ProductCreate(supplier_id=supplier.id, name="Widget", quantity=Decimal("10"), price=Decimal("5.00")),
                owner,
                session,
            )
            assert created.requested_amount is None
            assert created.paid_amount is None
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id], supplier.id)


@pytest.mark.asyncio
async def test_product_reflects_requested_and_prorated_paid_amounts():
    client, owner, other, observer, supplier, order = await _setup()
    try:
        async with async_session_factory() as session:
            created = await create_product(
                order.id,
                ProductCreate(supplier_id=supplier.id, name="Widget", quantity=Decimal("10"), price=Decimal("10.00")),
                owner,
                session,
            )

        async with async_session_factory() as session:
            request = await create_payment_request(
                order.id,
                PaymentRequestCreate(items=[PaymentRequestItemIn(product_id=created.id, amount=Decimal("40.00"))]),
                owner,
                session,
            )

        async with async_session_factory() as session:
            await create_payment(
                order.id,
                request.id,
                PaymentCreate(amount=Decimal("20.00"), exchange_rate=Decimal("1")),
                owner,
                session,
            )

        async with async_session_factory() as session:
            listed = await list_products(order.id, owner, session)
            product = next(p for p in listed if p.id == created.id)
            assert product.requested_amount == Decimal("40.00")
            # Single item spans the whole request, so its prorated share is the full paid amount.
            assert product.paid_amount == Decimal("20.00")
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id], supplier.id)


@pytest.mark.asyncio
async def test_product_reflects_shipped_and_accepted_quantities():
    client, owner, other, observer, supplier, order = await _setup()
    extra_user_ids: list[int] = []
    try:
        # Only an admin may accept a shipment.
        async with async_session_factory() as session:
            admin = User(
                login="prod_ship_admin", password_hash=hash_password("x"), role=UserRole.admin, full_name="Ship Admin"
            )
            session.add(admin)
            await session.commit()
            await session.refresh(admin)
            extra_user_ids.append(admin.id)

        async with async_session_factory() as session:
            created = await create_product(
                order.id,
                ProductCreate(supplier_id=supplier.id, name="Widget", quantity=Decimal("10"), price=Decimal("5.00")),
                owner,
                session,
            )

        async with async_session_factory() as session:
            listed = await list_products(order.id, owner, session)
            product = next(p for p in listed if p.id == created.id)
            assert product.shipped_quantity == Decimal("0")
            assert product.accepted_quantity == Decimal("0")
            assert product.shipments == []

        async with async_session_factory() as session:
            first = await create_logistics(
                order.id,
                LogisticsCreate(
                    items=[LogisticsItemIn(product_id=created.id, quantity=Decimal("4"))],
                    tracking="PRODSUM-A", ship_date=datetime.now(UTC)
                ),
                owner,
                session,
            )

        async with async_session_factory() as session:
            second = await create_logistics(
                order.id,
                LogisticsCreate(
                    items=[LogisticsItemIn(product_id=created.id, quantity=Decimal("6"))],
                    tracking="PRODSUM-B", ship_date=datetime.now(UTC)
                ),
                owner,
                session,
            )

        async with async_session_factory() as session:
            await accept_logistics(
                order.id,
                second.id,
                LogisticsAccept(
                    received_date=datetime.now(UTC),
                    expense_amount=Decimal("10.00"),
                    currency="USD",
                    exchange_rate=Decimal("1"),
                ),
                admin,
                session,
            )

        async with async_session_factory() as session:
            listed = await list_products(order.id, owner, session)
            product = next(p for p in listed if p.id == created.id)
            assert product.shipped_quantity == Decimal("10")
            assert product.accepted_quantity == Decimal("6")
            assert {s.tracking for s in product.shipments} == {"PRODSUM-A", "PRODSUM-B"}

        # A cancelled shipment frees its quantity again but stays visible in the list.
        async with async_session_factory() as session:
            await update_logistics(order.id, first.id, LogisticsUpdate(status="cancelled"), owner, session)

        async with async_session_factory() as session:
            listed = await list_products(order.id, owner, session)
            product = next(p for p in listed if p.id == created.id)
            assert product.shipped_quantity == Decimal("6")
            assert product.accepted_quantity == Decimal("6")
            assert len(product.shipments) == 2
    finally:
        await _cleanup(client.id, [owner.id, other.id, observer.id, *extra_user_ids], supplier.id)
