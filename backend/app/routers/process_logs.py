from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.models.user import User, UserRole
from app.routers.auth import require_role
from app.schemas.process_logs import LogSourcesOut, ProcessLogsOut
from app.services import docker_logs

router = APIRouter(prefix="/api/process-logs", tags=["process_logs"])


@router.get("/sources", response_model=LogSourcesOut)
async def list_process_log_sources(
    _admin: User = require_role(UserRole.admin),
) -> dict:
    """Список процессов проекта для выбора «чьи логи смотреть».

    Деградирует мягко: если прокси недоступен или функция выключена — отдаёт
    ``available=false`` с пояснением, а не 500, чтобы страница не падала.
    """
    try:
        items = docker_logs.list_sources()
    except docker_logs.LogsUnavailable as e:
        return {"items": [], "available": False, "detail": str(e)}
    return {"items": items, "available": True, "levels": docker_logs.LEVELS}


@router.get("/", response_model=ProcessLogsOut)
async def get_process_logs(
    source: str = Query(..., description="имя сервиса/контейнера из /sources"),
    since: datetime | None = Query(default=None, description="ISO: от какого времени"),
    until: datetime | None = Query(default=None, description="ISO: до какого времени"),
    level: list[str] | None = Query(default=None, description="фильтр по уровням"),
    q: str | None = Query(default=None, description="подстрока в тексте лога"),
    tail: int = Query(default=500, ge=1, le=5000),
    _admin: User = require_role(UserRole.admin),
) -> dict:
    try:
        lines = docker_logs.read_logs(
            source, since=since, until=until, tail=tail, search=q, levels=level,
        )
    except docker_logs.UnknownSource:
        raise HTTPException(status_code=404, detail="Неизвестный источник логов") from None
    except docker_logs.LogsUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    return {
        "source": source,
        "lines": lines,
        "count": len(lines),
        "truncated": len(lines) >= tail,
    }
