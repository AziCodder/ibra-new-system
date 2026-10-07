from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.order import Order, OrderStatus
from app.models.order_calculation import OrderCalculationParticipant
from app.models.user import User, UserRole
from app.routers.auth import get_current_user, require_role
from app.schemas.order_calculation import CalculationIn, CalculationOut, CalculationParticipantOut
from app.services.action_log import log_action
from app.services.order_access import get_order_for_read
from app.services.profit import calculate_profit

router = APIRouter(prefix="/api/orders/{order_id}/calculation", tags=["order_calculation"])

_CENT = Decimal("0.01")


def split_profit(profit: Decimal, percents: list[Decimal]) -> list[Decimal]:
    """Each participant's share, to the cent.

    The rounding remainder goes to the last participant, so the shares always
    add up to exactly the profit (100.00 at 33.33/33.33/33.34 -> 33.33/33.33/33.34).
    """
    shares = [(profit * percent / 100).quantize(_CENT, rounding=ROUND_HALF_UP) for percent in percents]
    shares[-1] += profit - sum(shares)
    return shares


async def _get_order_locked(order_id: int, session: AsyncSession) -> Order:
    # Two admins saving at once, or one saving while another cancels, must not interleave.
    order = (
        await session.execute(select(Order).where(Order.id == order_id).with_for_update())
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


async def _to_calculation_out(order: Order, session: AsyncSession) -> CalculationOut:
    if order.calculated_at is None:
        breakdown = await calculate_profit(order.id, session)
        return CalculationOut(
            is_calculated=False,
            calculated_at=None,
            profit=breakdown.profit.quantize(_CENT) if breakdown.is_ready else None,
            currency=order.currency,
            is_ready=breakdown.is_ready,
            participants=[],
        )

    rows = (
        await session.execute(
            select(OrderCalculationParticipant, User.full_name, User.login)
            .join(User, OrderCalculationParticipant.user_id == User.id)
            .where(OrderCalculationParticipant.order_id == order.id)
            .order_by(OrderCalculationParticipant.id)
        )
    ).all()
    return CalculationOut(
        is_calculated=True,
        calculated_at=order.calculated_at,
        profit=order.calculated_profit,
        currency=order.currency,
        is_ready=True,
        participants=[
            CalculationParticipantOut(
                user_id=participant.user_id,
                full_name=full_name or login,
                percent=participant.percent,
                amount=participant.amount,
            )
            for participant, full_name, login in rows
        ],
    )


@router.get("/", response_model=CalculationOut)
async def get_calculation(
    order_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    order = await get_order_for_read(order_id, user, session)
    return await _to_calculation_out(order, session)


@router.post("/", response_model=CalculationOut)
async def calculate_order(
    order_id: int,
    body: CalculationIn,
    admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
):
    """Share a completed order's profit between staff by percentage, then freeze the order.

    The shares are fixed in money at this moment; while the calculation stands the
    order can't change (order_access.ensure_not_calculated), so they can't drift.
    """
    order = await _get_order_locked(order_id, session)
    if order.calculated_at is not None:
        raise HTTPException(status_code=409, detail="Заказ уже рассчитан")
    if order.status != OrderStatus.completed:
        raise HTTPException(status_code=409, detail="Рассчитать можно только завершённый заказ")

    user_ids = [participant.user_id for participant in body.participants]
    if len(set(user_ids)) != len(user_ids):
        raise HTTPException(status_code=422, detail="Каждого участника можно добавить только один раз")
    if sum(participant.percent for participant in body.participants) != Decimal("100"):
        raise HTTPException(status_code=422, detail="Сумма процентов участников должна быть ровно 100")

    staff = (await session.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
    names = {u.id: u.full_name or u.login for u in staff if u.role in (UserRole.admin, UserRole.manager)}
    if len(names) != len(user_ids):
        raise HTTPException(status_code=422, detail="Участниками могут быть только администраторы и менеджеры")

    breakdown = await calculate_profit(order_id, session)
    if not breakdown.is_ready:
        raise HTTPException(
            status_code=409,
            detail="Прибыль ещё не итоговая: не вся логистика принята или не все товары оплачены полностью",
        )

    profit = breakdown.profit.quantize(_CENT)
    amounts = split_profit(profit, [participant.percent for participant in body.participants])
    session.add_all(
        [
            OrderCalculationParticipant(
                order_id=order.id, user_id=participant.user_id, percent=participant.percent, amount=amount
            )
            for participant, amount in zip(body.participants, amounts, strict=True)
        ]
    )
    order.calculated_at = datetime.now(UTC)
    order.calculated_profit = profit
    await log_action(
        session,
        admin,
        "order.calculated",
        "order",
        order.id,
        ", ".join(f"{names[participant.user_id]} {participant.percent}%" for participant in body.participants),
    )
    await session.commit()
    await session.refresh(order)
    return await _to_calculation_out(order, session)


@router.delete("/", status_code=204)
async def cancel_calculation(
    order_id: int,
    admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
):
    """Wipe the calculation and unfreeze the order; a no-op if it isn't calculated."""
    order = await _get_order_locked(order_id, session)
    if order.calculated_at is None:
        return

    await session.execute(
        delete(OrderCalculationParticipant).where(OrderCalculationParticipant.order_id == order.id)
    )
    order.calculated_at = None
    order.calculated_profit = None
    await log_action(session, admin, "order.calculation_cancelled", "order", order.id)
    await session.commit()
