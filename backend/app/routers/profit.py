from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.order import Order
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.services.order_metrics import snapshot_order_metrics
from app.services.profit import calculate_profit

router = APIRouter(prefix="/api/orders", tags=["profit"])


class ProfitBreakdownOut(BaseModel):
    income: Decimal
    purchases: Decimal
    logistics: Decimal
    other_expenses: Decimal
    profit: Decimal
    currency: str
    is_ready: bool
    profit_pct: Decimal | None
    processing_days: int | None


@router.get("/{order_id}/profit", response_model=ProfitBreakdownOut)
async def get_order_profit(
    order_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    order = (await session.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if user.role == UserRole.manager and order.manager_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")

    breakdown = await calculate_profit(order_id, session)
    if breakdown.is_ready:
        await snapshot_order_metrics(order_id, session, breakdown=breakdown)
        await session.commit()
        await session.refresh(order)

    return ProfitBreakdownOut(
        income=breakdown.income,
        purchases=breakdown.purchases,
        logistics=breakdown.logistics,
        other_expenses=breakdown.other_expenses,
        profit=breakdown.profit,
        currency=breakdown.currency,
        is_ready=breakdown.is_ready,
        profit_pct=order.profit_pct,
        processing_days=order.processing_days,
    )
