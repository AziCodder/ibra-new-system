from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.user import User, UserRole
from app.routers.auth import require_role
from app.schemas.system_health import HealthReportOut
from app.services import system_health

router = APIRouter(prefix="/api/system-health", tags=["system_health"])


@router.get("/", response_model=HealthReportOut)
async def get_system_health(
    _admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await system_health.collect(session)
