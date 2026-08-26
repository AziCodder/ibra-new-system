"""Состояние системы для админ-панели («Состояние системы»).

Сводит здоровье инфраструктуры и HTTP-пробы ключевых страниц фронта и
публичных эндпоинтов бэкенда с их статус-кодами и временем ответа.

Инфраструктура — это бэкенд, база, фронтенд, ОБА узла кластера (свой с ролью
и отставанием реплики, соседний по его адресу) и ОБА хранилища вложений.
Показывать одно «файловое хранилище» на два независимых бакета бессмысленно:
смысл второго ровно в том, чтобы пережить отказ первого, а значит их
состояния нужно видеть порознь.

Каждая проверка изолирована (не поднимает исключение наружу): сбой одной не
роняет остальные и не валит сам эндпоинт.

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


async def _check_local_storage() -> dict:
    t0 = time.perf_counter()
    try:
        await asyncio.to_thread(_storage_probe)
        return {"name": "storage", "label": "Файловое хранилище", "status": "ok", "latency_ms": _ms(t0)}
    except Exception as exc:  # noqa: BLE001
        return {"name": "storage", "label": "Файловое хранилище", "status": "down", "detail": str(exc)[:200]}


async def _check_bucket(name: str, config) -> dict:
    """Проверка одного бакета: реальный запрос к S3, а не чтение конфига."""
    from app.services.s3 import S3Bucket

    label = config.label or name
    if not config.configured:
        return {
            "name": name,
            "label": label,
            "status": "down" if name == "s3_primary" else "warn",
            "detail": "не настроено",
        }
    t0 = time.perf_counter()
    try:
        await S3Bucket(config).ping()
        return {"name": name, "label": label, "status": "ok", "latency_ms": _ms(t0),
                "detail": config.bucket}
    except Exception as exc:  # noqa: BLE001
        return {"name": name, "label": label, "status": "down", "latency_ms": _ms(t0),
                "detail": str(exc)[:200]}


async def _check_storage() -> list[dict]:
    """Хранилище вложений: локальная папка либо два независимых бакета.

    Раньше здесь всегда проверялась папка на диске — даже когда файлы давно
    уехали в S3. Карточка горела зелёным, ничего не зная о бакетах: отказ
    хранилища не был виден в админке вообще.
    """
    if settings.storage_backend != "s3":
        return [await _check_local_storage()]
    return list(
        await asyncio.gather(
            _check_bucket("s3_primary", settings.s3_primary_config),
            _check_bucket("s3_mirror", settings.s3_mirror_config),
        )
    )


async def _check_cluster() -> list[dict]:
    """Оба узла кластера: этот и соседний, с ролями и отставанием реплики.

    Роль спрашивается у базы, а не берётся из конфига: после переключения
    конфиг сказал бы неправду. Сосед проверяется по своему адресу — тем же
    способом, каким это делает сторож, принимающий решение о перехвате.
    """
    from app.services import cluster

    if not settings.peer_url:
        return []
    try:
        state = await cluster.snapshot()
        status, detail = cluster.health(state)
    except Exception as exc:  # noqa: BLE001
        return [{"name": "node_self", "label": f"Сервер {settings.node_name}",
                 "status": "down", "detail": str(exc)[:200]}]

    role = "главный" if state["role"] == cluster.PRIMARY else "резерв"
    services = [{
        "name": "node_self",
        "label": f"Сервер {settings.node_name} · {role}",
        "status": status,
        "detail": detail,
    }]

    peer = state.get("peer") or {}
    alive = bool(peer.get("alive"))
    # Сосед отвечает — значит он жив как машина. Какая у него роль, отсюда
    # не видно: спрашивать об этом мёртвый узел бессмысленно, а живой ответит
    # на своей же странице состояния.
    services.append({
        "name": "node_peer",
        "label": "Второй сервер",
        "status": "ok" if alive else "down",
        "latency_ms": peer.get("latency_ms"),
        "detail": "отвечает" if alive else (peer.get("detail") or "не отвечает")[:200],
    })
    return services


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
        (db_check, storage_checks, frontend_check, cluster_checks), pages, apis = await asyncio.gather(
            asyncio.gather(
                _check_database(session),
                _check_storage(),
                _check_frontend(client, fe_base),
                _check_cluster(),
            ),
            asyncio.gather(*[_probe(client, name=p, url=fe_base + p, kind="page") for p in FRONTEND_PAGES]),
            asyncio.gather(*[_probe(client, name=p, url=be_base + p, kind="api") for p in API_ENDPOINTS]),
        )
    finally:
        if own_client:
            await client.aclose()

    services = [
        _check_backend(),
        db_check,
        frontend_check,
        *cluster_checks,
        *storage_checks,
    ]
    all_pages = [*pages, *apis]
    return {
        "enabled": True,
        "overall": overall_status([*services, *all_pages]),
        "services": services,
        "pages": all_pages,
        "checked_at": datetime.now(UTC),
    }
