"""Состояние кластера для админки и для соседнего узла.

``/api/cluster/ping`` намеренно открыт без авторизации: именно по нему второй
сервер проверяет, жив ли первый, и сессии у него нет. Отдаёт он только роль
узла и его имя — ничего, что стоило бы прятать.
"""

from fastapi import APIRouter

from app.core.config import settings
from app.models.user import User, UserRole
from app.routers.auth import require_role
from app.services import cluster

router = APIRouter(prefix="/api/cluster", tags=["cluster"])


@router.get("/ping")
async def cluster_ping() -> dict:
    """Лёгкая проба для соседа: отвечаем — значит живы."""
    try:
        role = await cluster.role()
    except Exception:  # noqa: BLE001 — база лежит, но сам узел ответить обязан
        role = "unknown"
    return {"node": settings.node_name, "role": role}


@router.get("/")
async def cluster_state(_admin: User = require_role(UserRole.admin)) -> dict:
    state = await cluster.snapshot()
    status, detail = cluster.health(state)
    return {**state, "status": status, "detail": detail}
