from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.database import get_session
from app.models.client import Client
from app.models.order import Order, OrderStatus
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest, PaymentRequestItem
from app.models.product import Product
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.payment import PaymentCreate, PaymentOut
from app.schemas.payment_request import PaymentRequestItemOut, PaymentRequestSummaryOut
from app.services.payment_notifications import notify_payment_recorded
from app.services.payment_remaining import get_payment_request_paid

router = APIRouter(prefix="/api/payment-requests", tags=["payment_requests_global"])

ManagerUser = aliased(User, name="manager_user")


async def _to_summary_out(
    request: PaymentRequest,
    order: Order,
    client: Client,
    manager: User,
    session: AsyncSession,
) -> PaymentRequestSummaryOut:
    creator = (await session.execute(select(User).where(User.id == request.created_by_id))).scalar_one()

    rows = (
        await session.execute(
            select(PaymentRequestItem, Product.name, Product.currency)
            .join(Product, PaymentRequestItem.product_id == Product.id)
            .where(PaymentRequestItem.payment_request_id == request.id)
        )
    ).all()

    items = [
        PaymentRequestItemOut(id=item.id, product_id=item.product_id, product_name=product_name, amount=item.amount)
        for item, product_name, _ in rows
    ]
    currency = rows[0][2] if rows else ""
    total_amount = sum((item.amount for item in items), start=Decimal("0"))
    paid_amount = await get_payment_request_paid(session, request.id)

    return PaymentRequestSummaryOut(
        id=request.id,
        order_id=request.order_id,
        created_by_id=request.created_by_id,
        created_by_name=creator.full_name,
        requisites=request.requisites,
        details=request.details,
        priority=request.priority,
        file_keys=request.file_keys,
        currency=currency,
        total_amount=total_amount,
        paid_amount=paid_amount,
        remaining_amount=total_amount - paid_amount,
        items=items,
        created_at=request.created_at,
        order_number=order.number,
        client_name=client.full_name,
        manager_name=manager.full_name,
        manager_id=order.manager_id,
        order_currency=order.currency,
    )


@router.get("/", response_model=list[PaymentRequestSummaryOut])
async def list_all_payment_requests(
    manager_id: int | None = Query(default=None),
    client_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    sort: Literal["asc", "desc"] = Query(default="desc"),
    # This page is a worklist — "what still has to be paid" — so settled requests
    # are hidden unless explicitly asked for.
    remaining: Literal["positive", "all"] = Query(default="positive"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[PaymentRequestSummaryOut]:
    stmt = (
        select(PaymentRequest, Order, Client, ManagerUser)
        .join(Order, PaymentRequest.order_id == Order.id)
        .join(Client, Order.client_id == Client.id)
        .join(ManagerUser, Order.manager_id == ManagerUser.id)
        # A cancelled order is never going to be paid, so its requests are noise
        # on this page. They stay visible inside the order itself.
        .where(Order.status != OrderStatus.cancelled)
    )

    if user.role == UserRole.manager:
        stmt = stmt.where(Order.manager_id == user.id)

    if manager_id is not None:
        stmt = stmt.where(Order.manager_id == manager_id)
    if client_id is not None:
        stmt = stmt.where(Order.client_id == client_id)
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(Order.number.ilike(like), Client.full_name.ilike(like)))

    stmt = stmt.order_by(
        PaymentRequest.created_at.desc() if sort == "desc" else PaymentRequest.created_at.asc()
    )

    rows = (await session.execute(stmt)).all()
    summaries = [await _to_summary_out(pr, order, client, mgr, session) for pr, order, client, mgr in rows]

    # remaining_amount is derived from the payments (see _to_summary_out), not a
    # column, so the filter runs here rather than in the query.
    if remaining == "positive":
        summaries = [s for s in summaries if s.remaining_amount > 0]
    return summaries


@router.post("/{request_id}/payments", response_model=PaymentOut, status_code=201)
async def add_payment_global(
    request_id: int,
    body: PaymentCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PaymentOut:
    if user.role == UserRole.observer:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    pr = (await session.execute(select(PaymentRequest).where(PaymentRequest.id == request_id))).scalar_one_or_none()
    if not pr:
        raise HTTPException(status_code=404, detail="Payment request not found")

    if user.role == UserRole.manager:
        order = (await session.execute(select(Order).where(Order.id == pr.order_id))).scalar_one()
        if order.manager_id != user.id:
            raise HTTPException(status_code=404, detail="Payment request not found")

    payment = Payment(
        payment_request_id=request_id,
        author_id=user.id,
        amount=body.amount,
        currency=body.currency,
        exchange_rate=body.exchange_rate,
        file_key=body.file_key,
        note=body.note,
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    await notify_payment_recorded(payment, session)
    return PaymentOut(
        id=payment.id,
        payment_request_id=payment.payment_request_id,
        author_id=payment.author_id,
        author_name=user.full_name,
        amount=payment.amount,
        currency=payment.currency,
        exchange_rate=payment.exchange_rate,
        file_key=payment.file_key,
        note=payment.note,
        created_at=payment.created_at,
    )
