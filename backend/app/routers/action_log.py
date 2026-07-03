from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.action_log import ActionLog
from app.models.user import User, UserRole
from app.routers.auth import require_role
from app.schemas.action_log import ActionLogOut

router = APIRouter(prefix="/api/action-log", tags=["action_log"])


@router.get("/", response_model=list[ActionLogOut])
async def list_action_log(
    entity_type: str | None = Query(default=None),
    actor_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    _admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
) -> list[ActionLogOut]:
    """Recent key-operation audit trail (admin only) for dispute investigation.

    Filter by ``entity_type`` (e.g. ``order``, ``logistics``) or ``actor_id``.
    """
    stmt = (
        select(ActionLog, User.full_name)
        .join(User, ActionLog.actor_id == User.id)
        .order_by(ActionLog.created_at.desc())
        .limit(limit)
    )
    if entity_type is not None:
        stmt = stmt.where(ActionLog.entity_type == entity_type)
    if actor_id is not None:
        stmt = stmt.where(ActionLog.actor_id == actor_id)

    rows = (await session.execute(stmt)).all()
    return [
        ActionLogOut(
            id=entry.id,
            actor_id=entry.actor_id,
            actor_name=actor_name,
            action=entry.action,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            details=entry.details,
            created_at=entry.created_at,
        )
        for entry, actor_name in rows
    ]
