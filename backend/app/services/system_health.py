"""Состояние системы для админ-панели («Состояние системы»).

Сводит здоровье инфраструктуры (бэкенд, БД, файловое хранилище, фронтенд) и
HTTP-пробы ключевых страниц фронта и публичных эндпоинтов бэкенда с их
статус-кодами и временем ответа. Каждая проверка изолирована (не поднимает
исключение наружу): сбой одной не роняет остальные и не валит сам эндпоинт.

Статусы: ``ok`` | ``warn`` | ``down``. Итоговый ``overall`` — худший из всех.
"""

from __future__ import annotations

import asyncio
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

PROBE_TIMEOUT = 4.0  # сек на одну HTTP-пробу

# Ключевые страницы фронта и публичные эндпоинты бэкенда (курируемый
# список — расширяется по мере роста приложения).
FRONTEND_PAGES = ["/", "/login", "/database", "/payment-requests", "/logistics"]
API_ENDPOINTS = ["/health", "/health/live", "/health/ready"]

_STARTED = time.time()  # ≈ старт процесса (импорт модуля при загрузке приложения)


def _ms(t0: float) -> int:
    return round((time.perf_counter() - t0) * 1000)


def status_for_code(code: int) -> str:
    """HTTP-код → статус проверки: <400 ok, 4xx warn, >=500 down."""
    if code < 400:
        return "ok"
    return "warn" if code < 500 else "down"


def overall_status(checks: list[dict]) -> str:
    """Худший статус среди всех проверок."""
    statuses = {c.get("status") for c in checks}
    if "down" in statuses:
        return "down"
    if "warn" in statuses:
        return "warn"
    return "ok"


# ──────────────────────────────────────────────────────────── проверки сервисов


def _check_backend() -> dict:
    # Раз этот код выполняется — бэкенд жив по определению.
    return {
        "name": "backend",
        "label": "Бэкенд (API)",
        "status": "ok",
        "latency_ms": 0,
        "detail": f"uptime {round(time.time() - _STARTED)} c",
    }


async def _check_database(session: AsyncSession) -> dict:
    t0 = time.perf_counter()
    try:
        await session.execute(text("SELECT 1"))
        return {"name": "database", "label": "PostgreSQL", "status": "ok", "latency_ms": _ms(t0)}
    except Exception as exc:  # noqa: BLE001 — health probe must not raise
        return {"name": "database", "label": "PostgreSQL", "status": "down", "detail": str(exc)[:200]}


def _storage_probe() -> None:
    base = Path(settings.upload_dir)
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=base, prefix=".health_"):
        pass


async def _check_storage() -> dict:
    t0 = time.perf_counter()
    try:
        await asyncio.to_thread(_storage_probe)
        return {"name": "storage", "label": "Файловое хранилище", "status": "ok", "latency_ms": _ms(t0)}
    except Exception as exc:  # noqa: BLE001
        return {"name": "storage", "label": "Файловое хранилище", "status": "down", "detail": str(exc)[:200]}


async def _probe(client: httpx.AsyncClient, *, name: str, url: str, kind: str) -> dict:
    """Одна HTTP-проба: статус-код + время ответа (или ошибка соединения)."""
    t0 = time.perf_counter()
    try:
        response = await client.get(url, follow_redirects=True)
        return {
            "name": name,
            "kind": kind,
            "status_code": response.status_code,
            "status": status_for_code(response.status_code),
            "latency_ms": _ms(t0),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "name": name,
            "kind": kind,
            "status_code": None,
            "status": "down",
            "latency_ms": _ms(t0),
            "detail": str(exc)[:200],
        }


async def _check_frontend(client: httpx.AsyncClient, base: str) -> dict:
    probe = await _probe(client, name="frontend", url=f"{base}/", kind="page")
    code = probe.get("status_code")
    return {
        "name": "frontend",
        "label": "Фронтенд",
        "status": probe["status"],
        "latency_ms": probe["latency_ms"],
        "detail": probe.get("detail") or (f"HTTP {code}" if code is not None else "недоступен"),
    }


async def collect(session: AsyncSession, *, client: httpx.AsyncClient | None = None) -> dict:
    """Собрать полную сводку состояния системы."""
    if not settings.health_check_enabled:
        return {
            "enabled": False,
            "overall": "ok",
            "services": [],
            "pages": [],
            "checked_at": datetime.now(UTC),
        }

    fe_base = settings.health_frontend_base.rstrip("/")
    be_base = settings.health_self_base.rstrip("/")

    own_client = client is None
    client = client or httpx.AsyncClient(timeout=PROBE_TIMEOUT)
    try:
        (db_check, storage_check, frontend_check), pages, apis = await asyncio.gather(
            asyncio.gather(_check_database(session), _check_storage(), _check_frontend(client, fe_base)),
            asyncio.gather(*[_probe(client, name=p, url=fe_base + p, kind="page") for p in FRONTEND_PAGES]),
            asyncio.gather(*[_probe(client, name=p, url=be_base + p, kind="api") for p in API_ENDPOINTS]),
        )
    finally:
        if own_client:
            await client.aclose()

    services = [_check_backend(), db_check, storage_check, frontend_check]
    all_pages = [*pages, *apis]
    return {
        "enabled": True,
        "overall": overall_status([*services, *all_pages]),
        "services": services,
        "pages": all_pages,
        "checked_at": datetime.now(UTC),
    }
