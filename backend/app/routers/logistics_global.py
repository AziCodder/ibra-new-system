from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.database import get_session
from app.models.client import Client
from app.models.logistics import Logistics, LogisticsItem, LogisticsStatus
from app.models.order import Order
from app.models.product import Product
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.logistics import LogisticsItemOut, LogisticsSummaryOut
from app.services.logistics_items import get_logistics_items

router = APIRouter(prefix="/api/logistics", tags=["logistics_global"])

ManagerUser = aliased(User, name="manager_user")
CreatorUser = aliased(User, name="creator_user")


@router.get("/", response_model=list[LogisticsSummaryOut])
async def list_all_logistics(
    status: LogisticsStatus | None = Query(default=None),
    client_id: int | None = Query(default=None),
    manager_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    sort: Literal["asc", "desc"] = Query(default="desc"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[LogisticsSummaryOut]:
    stmt = (
        select(Logistics, Order, Client, ManagerUser, CreatorUser)
        .join(Order, Logistics.order_id == Order.id)
        .join(Client, Order.client_id == Client.id)
        .join(ManagerUser, Order.manager_id == ManagerUser.id)
        .join(CreatorUser, Logistics.created_by_id == CreatorUser.id)
    )

    if user.role == UserRole.manager:
        stmt = stmt.where(Order.manager_id == user.id)

    if status is not None:
        stmt = stmt.where(Logistics.status == status)
    if client_id is not None:
        stmt = stmt.where(Order.client_id == client_id)
    if manager_id is not None:
        stmt = stmt.where(Order.manager_id == manager_id)
    if search:
        term = f"%{search}%"
        # A shipment now carries several products, so the product-name match is an
        # EXISTS over its lines rather than a join (which would duplicate rows).
        matches_product = (
            select(LogisticsItem.id)
            .join(Product, LogisticsItem.product_id == Product.id)
            .where(LogisticsItem.logistics_id == Logistics.id, Product.name.ilike(term))
            .exists()
        )
        stmt = stmt.where(
            or_(
                Logistics.tracking.ilike(term),
                Order.number.ilike(term),
                matches_product,
            )
        )

    stmt = stmt.order_by(
        Logistics.created_at.desc() if sort == "desc" else Logistics.created_at.asc()
    )

    rows = (await session.execute(stmt)).all()
    lines_by_logistics = await get_logistics_items(session, [lg.id for lg, *_ in rows])
    return [
        LogisticsSummaryOut(
            id=lg.id,
            order_id=lg.order_id,
            items=[
                LogisticsItemOut(product_id=line.product_id, product_name=line.product_name, quantity=line.quantity)
                for line in lines_by_logistics.get(lg.id, [])
            ],
            created_by_id=lg.created_by_id,
            created_by_name=creator.full_name,
            total_quantity=sum(
                (line.quantity for line in lines_by_logistics.get(lg.id, [])), start=Decimal("0")
            ),
            tracking=lg.tracking,
            ship_date=lg.ship_date,
            invoice_file_key=lg.invoice_file_key,
            details=lg.details,
            status=lg.status,
            received_date=lg.received_date,
            expense_amount=lg.expense_amount,
            currency=lg.currency,
            exchange_rate=lg.exchange_rate,
            acceptance_note=lg.acceptance_note,
            created_at=lg.created_at,
            order_number=order.number,
            order_currency=order.currency,
            client_name=client.full_name,
            manager_name=manager.full_name,
            manager_id=order.manager_id,
        )
        for lg, order, client, manager, creator in rows
    ]
