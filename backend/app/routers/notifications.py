from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.notification_log import NotificationLog, NotificationStatus
from app.models.user import User, UserRole
from app.routers.auth import require_role
from app.schemas.notification_log import NotificationLogOut

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/log", response_model=list[NotificationLogOut])
async def list_notification_log(
    status: NotificationStatus | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    _admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
) -> list[NotificationLog]:
    """Recent outbound-notification delivery outcomes (admin only).

    Filter with ``status=failed`` to see undelivered ("не доставлено")
    messages — the visible side of Phase 11.5's failure handling.
    """
    stmt = select(NotificationLog).order_by(NotificationLog.created_at.desc()).limit(limit)
    if status is not None:
        stmt = stmt.where(NotificationLog.status == status)
    return list((await session.execute(stmt)).scalars().all())
