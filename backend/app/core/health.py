"""Health / uptime probes for monitoring."""

from __future__ import annotations

from sqlalchemy import text

from app.core.config import settings
from app.core.database import async_session_factory


async def check_database() -> tuple[bool, str | None]:
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # noqa: BLE001 — health probe must not raise
        return False, str(exc)


async def build_health_payload(*, deep: bool = False) -> dict:
    payload: dict = {
        "status": "ok",
        "service": "ibra-order-system",
        "version": "0.1.0",
        "env": settings.app_env,
        "db_configured": bool(settings.database_url),
    }
    if not deep:
        return payload

    db_ok, db_error = await check_database()
    payload["db"] = "ok" if db_ok else "error"
    if db_error:
        payload["db_error"] = db_error
    if not db_ok:
        payload["status"] = "degraded"
    return payload
