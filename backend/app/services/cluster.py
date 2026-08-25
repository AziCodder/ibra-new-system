"""Состояние кластера из двух серверов и операции над ним.

Роль узла нигде не записана в конфиге — её всегда говорит сама база:
``pg_is_in_recovery()`` истинно на реплике и ложно на главном. Конфиг мог бы
соврать (забыли поправить после переключения), база — нет.

Что здесь есть:

* ``snapshot`` — полная картина: роль, реплика, лаг, режим синхронности,
  доступность второго узла. На ней строятся и автоматика, и админка;
* ``set_sync`` — включение/выключение синхронной репликации на ходу. Нужно,
  чтобы упавший резерв не заморозил запись на рабочем сервере: синхронный
  режим означает «ждать второй сервер», а ждать мёртвого можно вечно;
* ``promote`` — повышение реплики до главного (``pg_promote``);
* ``set_read_only`` — мягкое самоограждение: узел, потерявший сеть, сам
  переходит в режим «только чтение», чтобы не разойтись с новым главным.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

import httpx
from sqlalchemy import text

from app.core.config import settings
from app.core.database import async_session_factory

logger = logging.getLogger(__name__)

PRIMARY = "primary"
STANDBY = "standby"


async def _scalar(sql: str):
    async with async_session_factory() as session:
        return (await session.execute(text(sql))).scalar()


async def role() -> str:
    """Кто мы сейчас — главный или резерв. Спрашиваем у базы, не у конфига."""
    return STANDBY if await _scalar("SELECT pg_is_in_recovery()") else PRIMARY


async def replicas() -> list[dict]:
    """Кто к нам подключён репликой (имеет смысл только на главном)."""
    async with async_session_factory() as session:
        rows = await session.execute(
            text(
                "SELECT application_name, state, sync_state, client_addr::text, "
                "COALESCE(pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn), 0)::bigint AS lag_bytes, "
                # replay_lag — насколько реплика отстала ПО ВРЕМЕНИ. В
                # асинхронном режиме это и есть размер возможной потери, и
                # объяснять его людям куда проще, чем байты WAL. NULL, когда
                # записей не было вовсе (реплика не отстаёт — ей нечего ждать).
                "EXTRACT(EPOCH FROM replay_lag) AS lag_seconds "
                "FROM pg_stat_replication"
            )
        )
        return [
            {
                "name": r.application_name,
                "state": r.state,
                "sync_state": r.sync_state,
                "address": r.client_addr,
                "lag_bytes": int(r.lag_bytes or 0),
                "lag_seconds": None if r.lag_seconds is None else float(r.lag_seconds),
            }
            for r in rows
        ]


async def replay_lag_seconds() -> float | None:
    """На сколько отстаёт реплика (имеет смысл только на резерве)."""
    value = await _scalar(
        "SELECT CASE WHEN pg_is_in_recovery() "
        "THEN EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) END"
    )
    return None if value is None else float(value)


async def sync_standby_names() -> str:
    return (await _scalar("SHOW synchronous_standby_names")) or ""


async def set_sync(enabled: bool) -> str:
    """Переключить синхронную репликацию.

    Возвращает новое значение ``synchronous_standby_names``. Пустая строка —
    асинхронный режим: главный больше никого не ждёт.
    """
    value = f"ANY 1 ({settings.sync_standby_name})" if enabled else ""
    async with async_session_factory() as session:
        # ALTER SYSTEM пишет в postgresql.auto.conf, поэтому режим переживает
        # перезапуск, а reload применяет его без разрыва соединений.
        await session.execute(text(f"ALTER SYSTEM SET synchronous_standby_names = '{value}'"))
        await session.execute(text("SELECT pg_reload_conf()"))
        await session.commit()
    logger.warning("синхронная репликация: %s", "включена" if enabled else "ВЫКЛЮЧЕНА (деградация)")
    return value


async def set_read_only(enabled: bool) -> None:
    """Самоограждение: узел перестаёт принимать запись, оставаясь на чтение."""
    async with async_session_factory() as session:
        await session.execute(
            text(f"ALTER SYSTEM SET default_transaction_read_only = {'on' if enabled else 'off'}")
        )
        await session.execute(text("SELECT pg_reload_conf()"))
        await session.commit()
    logger.warning("режим только для чтения: %s", "включён" if enabled else "снят")


async def read_only() -> bool:
    return (await _scalar("SHOW default_transaction_read_only")) == "on"


async def promote(wait_seconds: int = 60) -> bool:
    """Повысить реплику до главного. На главном — ничего не делает."""
    if await role() == PRIMARY:
        return True
    async with async_session_factory() as session:
        ok = (
            await session.execute(
                text(f"SELECT pg_promote(true, {int(wait_seconds)})")
            )
        ).scalar()
        await session.commit()
    logger.warning("повышение реплики до главного: %s", "успех" if ok else "НЕ УДАЛОСЬ")
    return bool(ok)


async def probe(url: str, timeout: float | None = None) -> dict:
    """HTTP-проба одного адреса: живо ли и за сколько отвечает."""
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            timeout=timeout or settings.peer_check_timeout, verify=False
        ) as client:
            response = await client.get(url)
        return {
            "url": url,
            "alive": response.status_code < 500,
            "status_code": response.status_code,
            "latency_ms": round((time.perf_counter() - started) * 1000),
        }
    except Exception as exc:  # noqa: BLE001 — проба не должна поднимать исключения
        return {
            "url": url,
            "alive": False,
            "status_code": None,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "detail": str(exc)[:200],
        }


async def peer() -> dict | None:
    """Состояние второго узла. None — адрес соседа не настроен."""
    if not settings.peer_url:
        return None
    return await probe(settings.peer_url.rstrip("/"))


async def have_internet() -> bool:
    """Есть ли связь с внешним миром.

    Ключевая проверка перед перехватом: если внешние точки тоже молчат,
    значит сеть потеряли мы сами, а не сосед. Перехватывать в такой
    ситуации — верный способ получить двух «главных» разом.
    """
    for url in settings.failover_external_probes:
        if (await probe(url, timeout=4.0))["alive"]:
            return True
    return False


async def snapshot() -> dict:
    """Полная картина кластера — и для автоматики, и для админки."""
    current = await role()
    data: dict = {
        "node": settings.node_name,
        "role": current,
        "read_only": await read_only(),
        "sync_enabled": bool(await sync_standby_names()),
        "sync_configured": settings.sync_replication,
        "failover_enabled": settings.failover_enabled,
        "checked_at": datetime.now(UTC),
        "replicas": [],
        "lag_seconds": None,
        "peer": await peer(),
    }
    if current == PRIMARY:
        data["replicas"] = await replicas()
    else:
        data["lag_seconds"] = await replay_lag_seconds()
    return data


def health(state: dict) -> tuple[str, str]:
    """Свести картину к одному статусу и человеческой фразе.

    Асинхронный режим — не поломка, если он выбран осознанно: серверы в разных
    странах, и ожидание соседа на каждой записи стоило бы десятки миллисекунд.
    Поэтому «асинхронно» само по себе не тревога, тревога — РАЗМЕР отставания:
    именно столько работы пропадёт, если главный исчезнет прямо сейчас.
    Отдельно ловится случай «реплики нет вовсе» — он одинаково плох в любом
    режиме и означает, что данные живут на одном сервере.
    """
    warn_after = settings.replication_lag_warn_seconds
    alert_after = settings.replication_lag_alert_seconds

    if state["role"] == PRIMARY:
        if state["read_only"]:
            return "down", "узел изолирован и переведён в режим только чтения"

        replicas = state["replicas"]
        if not replicas:
            # Второй узел настроен, но реплики нет — это авария независимо от
            # выбранного режима. Если кластера нет вовсе, это просто одиночный
            # сервер, и обещать ему отказоустойчивость никто не обещал.
            if state["sync_configured"] or state.get("peer") is not None:
                return "down", "реплики нет: данные пишутся только на один сервер"
            return "warn", "главный узел, реплика не настроена"

        if [r for r in replicas if r["sync_state"] == "sync"]:
            return "ok", "главный узел, реплика синхронна"

        if state["sync_configured"]:
            # Синхронный режим заказан, но не действует — либо сторож опустил
            # его из-за пропажи резерва, либо он не настроен на самой базе.
            return "warn", "реплика подключена, но синхронный режим не действует"

        lag = max((r.get("lag_seconds") or 0.0) for r in replicas)
        if lag > alert_after:
            return "down", (
                f"асинхронная реплика отстала на {round(lag)} с — "
                "столько данных потеряется при внезапной аварии"
            )
        if lag > warn_after:
            return "warn", f"асинхронная реплика отстаёт на {round(lag)} с"
        return "ok", f"главный узел, асинхронная реплика отстаёт на {round(lag, 1)} с"

    lag = state["lag_seconds"]
    if lag is None:
        return "warn", "резерв, отставание неизвестно"
    if lag > alert_after:
        return "down", f"резерв отстал на {round(lag)} с"
    if lag > warn_after:
        return "warn", f"резерв отстаёт на {round(lag)} с"
    return "ok", f"резерв в строю, отставание {round(lag, 1)} с"
