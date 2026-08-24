"""Резервное копирование базы: снятие, отправка в два S3, срок хранения, проверка.

Правила хранения заданы заказчиком и жёстко разведены по типам копий:

* ``hourly`` — временные, удаляются через ``BACKUP_HOURLY_RETENTION_DAYS``
  (по умолчанию 7 дней);
* ``daily``  — постоянные, не удаляются никогда и никакой чисткой не
  затрагиваются;
* ``manual`` — запущенные руками, хранятся как постоянные.

Каждая копия — это ``pg_dump`` в сжатом формате, посчитанная SHA-256 и
заливка в оба бакета. Локальный файл после успешной отправки в основной
бакет удаляется: диск сервера — перевалочный пункт, а не место хранения.

Отдельная задача (``verify_last``) ночью разворачивает свежий дамп в пустую
базу и считает строки. Без этого «бэкап есть» означает лишь «файл есть».
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import socket
import time
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import desc, select

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.backup_run import BackupKind, BackupRun, BackupStatus
from app.models.stored_file import ReplicaState
from app.services.s3 import S3Bucket, S3Error

logger = logging.getLogger(__name__)

# Таблицы, по которым сверяется восстановленный дамп. Пустой заказ или
# пропавшие пользователи — признак того, что копия непригодна.
VERIFY_TABLES = ("users", "orders", "clients")


class BackupError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def parse_database_url(url: str) -> dict[str, str]:
    """DATABASE_URL → параметры подключения для утилит postgres."""
    normalized = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    parsed = urlparse(normalized)
    if parsed.scheme not in {"postgresql", "postgres"} or not parsed.hostname or not parsed.path:
        raise ValueError(f"Unsupported DATABASE_URL: {url}")
    return {
        "host": parsed.hostname,
        "port": str(parsed.port or 5432),
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
        "dbname": parsed.path.lstrip("/"),
    }


def _pg_env(conn: dict[str, str]) -> dict[str, str]:
    env = os.environ.copy()
    if conn["password"]:
        env["PGPASSWORD"] = conn["password"]
    return env


async def _run_tool(cmd: list[str], env: dict[str, str], *, timeout: float = 1800) -> str:
    """Запустить утилиту postgres, вернуть stdout; ошибку поднять с текстом stderr."""
    process = await asyncio.create_subprocess_exec(
        *cmd, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        process.kill()
        raise BackupError(f"{cmd[0]}: превышено время ожидания ({timeout:.0f} c)") from None
    if process.returncode != 0:
        raise BackupError(f"{cmd[0]}: {stderr.decode(errors='replace').strip()[:500]}")
    return stdout.decode(errors="replace")


def backup_targets() -> list[tuple[str, S3Bucket]]:
    """Бакеты для бэкапов — те же реквизиты, но свой префикс ключей.

    Возвращаются парами (слот, бакет), чтобы состояние копии записывалось
    именно в своё поле, а не по порядковому номеру в списке.
    """
    targets = []
    for slot, config in (
        ("primary", settings.s3_primary_config),
        ("mirror", settings.s3_mirror_config),
    ):
        if settings.storage_backend == "s3" and config.configured:
            targets.append((slot, S3Bucket(replace(config, prefix=settings.backup_prefix))))
    return targets


def backup_buckets() -> list[S3Bucket]:
    return [bucket for _, bucket in backup_targets()]


# ─────────────────────────────────────────────────────────────── снятие копии


async def create(kind: BackupKind = BackupKind.hourly) -> dict:
    """Снять копию базы и отправить её в оба хранилища."""
    if not settings.backup_enabled:
        return {"enabled": False}

    started = time.perf_counter()
    stamp = _now().strftime("%Y%m%d_%H%M%S")
    # Хвост из случайных символов: две копии, снятые в одну и ту же секунду
    # (например, ручная поверх часовой), иначе получили бы один ключ и
    # молча затёрли друг друга в бакете.
    filename = f"ibra_{kind.value}_{stamp}_{uuid.uuid4().hex[:6]}.dump"
    object_key = f"{kind.value}/{filename}"
    target_dir = Path(settings.backup_dir) / kind.value
    target_dir.mkdir(parents=True, exist_ok=True)
    local_path = target_dir / filename

    async with async_session_factory() as session:
        run = BackupRun(
            kind=kind,
            status=BackupStatus.running,
            object_key=object_key,
            local_path=str(local_path),
            node=socket.gethostname(),
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        run_id = run.id

    try:
        await _dump(local_path)
        data = local_path.read_bytes()
        sha256 = hashlib.sha256(data).hexdigest()
        primary_state, mirror_state, upload_error = await _upload(object_key, data, sha256)
    except (BackupError, OSError) as exc:
        await _finish(run_id, status=BackupStatus.failed, error=str(exc), started=started)
        logger.error("бэкап %s не снят: %s", kind.value, exc)
        return {"enabled": True, "status": "failed", "error": str(exc), "id": run_id}

    # Локальная копия нужна лишь до отправки: место на сервере не резиновое,
    # а сам сервер и есть то, от чьей потери мы страхуемся.
    kept_local = True
    if primary_state == ReplicaState.ok:
        local_path.unlink(missing_ok=True)
        kept_local = False

    await _finish(
        run_id,
        status=BackupStatus.ok,
        started=started,
        size=len(data),
        sha256=sha256,
        primary_state=primary_state,
        mirror_state=mirror_state,
        local_path=str(local_path) if kept_local else "",
        error=upload_error,
    )
    logger.info(
        "бэкап %s готов: %s, %d байт, копий в S3: %s",
        kind.value,
        object_key,
        len(data),
        sum(1 for s in (primary_state, mirror_state) if s == ReplicaState.ok),
    )
    return {
        "enabled": True,
        "status": "ok",
        "id": run_id,
        "object_key": object_key,
        "size": len(data),
        "sha256": sha256,
    }


async def _dump(target: Path) -> None:
    conn = parse_database_url(settings.database_url)
    cmd = [
        "pg_dump",
        "-h", conn["host"],
        "-p", conn["port"],
        "-U", conn["user"],
        "-d", conn["dbname"],
        "--format=custom",  # сжатый формат: меньше файл и восстановление по частям
        "--no-owner",
        "--no-privileges",
        "-f", str(target),
    ]
    await _run_tool(cmd, _pg_env(conn))


async def _upload(object_key: str, data: bytes, sha256: str) -> tuple[ReplicaState, ReplicaState, str]:
    targets = backup_targets()
    if not targets:
        # S3 не настроен — копия остаётся на диске, и это надо честно
        # показывать в админке, а не выдавать за отказоустойчивость.
        return ReplicaState.disabled, ReplicaState.disabled, ""

    states = {"primary": ReplicaState.disabled, "mirror": ReplicaState.disabled}
    errors = []
    for slot, bucket in targets:
        try:
            await bucket.put(object_key, data, sha256=sha256, content_type="application/octet-stream")
            states[slot] = ReplicaState.ok
        except S3Error as exc:
            states[slot] = ReplicaState.error
            errors.append(f"{bucket.config.label}: {exc}")
            logger.warning("бэкап не залит в %s: %s", bucket.config.label, exc)
    return states["primary"], states["mirror"], "; ".join(errors)[:1000]


async def _finish(run_id: int, *, status: BackupStatus, started: float, **fields) -> None:
    async with async_session_factory() as session:
        run = await session.get(BackupRun, run_id)
        if run is None:
            return
        run.status = status
        run.finished_at = _now()
        run.duration_ms = round((time.perf_counter() - started) * 1000)
        for name, value in fields.items():
            setattr(run, name, value)
        await session.commit()


# ──────────────────────────────────────────────────────────── срок хранения


async def cleanup(retention_days: int | None = None) -> dict:
    """Удалить часовые копии старше срока хранения.

    Суточные и ручные не трогаются ни при каких условиях — это их смысл.
    """
    days = retention_days if retention_days is not None else settings.backup_hourly_retention_days
    cutoff = _now() - timedelta(days=days)
    buckets = backup_buckets()

    async with async_session_factory() as session:
        result = await session.execute(
            select(BackupRun).where(
                BackupRun.kind == BackupKind.hourly,
                BackupRun.deleted_at.is_(None),
                BackupRun.started_at < cutoff,
            )
        )
        expired = list(result.scalars())

    removed = failed = 0
    for run in expired:
        errors = []
        for bucket in buckets:
            try:
                await bucket.delete(run.object_key)
            except S3Error as exc:
                errors.append(str(exc))
        if run.local_path:
            Path(run.local_path).unlink(missing_ok=True)

        async with async_session_factory() as session:
            row = await session.get(BackupRun, run.id)
            if row is None:
                continue
            if errors:
                failed += 1
                row.error = "; ".join(errors)[:1000]
            else:
                removed += 1
                row.deleted_at = _now()
                row.local_path = ""
            await session.commit()

    return {"retention_days": days, "removed": removed, "failed": failed}


# ────────────────────────────────────────────────────── проверка восстановлением


async def verify_last(kind: BackupKind = BackupKind.daily) -> dict:
    """Развернуть последнюю копию в отдельную базу и пересчитать строки."""
    if not settings.backup_verify_enabled:
        return {"enabled": False}

    async with async_session_factory() as session:
        result = await session.execute(
            select(BackupRun)
            .where(
                BackupRun.kind == kind,
                BackupRun.status == BackupStatus.ok,
                BackupRun.deleted_at.is_(None),
            )
            .order_by(desc(BackupRun.started_at))
            .limit(1)
        )
        run = result.scalar_one_or_none()

    if run is None:
        return {"enabled": True, "status": "skipped", "detail": "нет копий для проверки"}

    conn = parse_database_url(settings.database_url)
    scratch = settings.backup_verify_database
    workdir = Path(settings.backup_dir) / "verify"
    workdir.mkdir(parents=True, exist_ok=True)
    dump_path = workdir / Path(run.object_key).name

    try:
        data = await _fetch(run)
        dump_path.write_bytes(data)
        detail = await _restore_and_count(conn, scratch, dump_path)
        status = BackupStatus.ok
    except (BackupError, S3Error, OSError) as exc:
        status = BackupStatus.failed
        detail = str(exc)[:1000]
        logger.error("проверка бэкапа %s провалилась: %s", run.object_key, exc)
    finally:
        dump_path.unlink(missing_ok=True)

    async with async_session_factory() as session:
        row = await session.get(BackupRun, run.id)
        if row is not None:
            row.verified_at = _now()
            row.verify_status = status
            row.verify_detail = detail
            await session.commit()

    return {"enabled": True, "status": status.value, "detail": detail, "id": run.id}


async def _fetch(run: BackupRun) -> bytes:
    """Взять тело копии: сперва из основного бакета, потом из зеркала, потом с диска."""
    for bucket in backup_buckets():
        try:
            return await bucket.get(run.object_key)
        except S3Error as exc:
            logger.warning("копия %s недоступна в %s: %s", run.object_key, bucket.config.label, exc)
    if run.local_path and Path(run.local_path).exists():
        return Path(run.local_path).read_bytes()
    raise BackupError("копия недоступна ни в одном хранилище")


async def _restore_and_count(conn: dict[str, str], scratch: str, dump_path: Path) -> str:
    env = _pg_env(conn)
    base = ["-h", conn["host"], "-p", conn["port"], "-U", conn["user"]]

    # Чистая база на каждый прогон: остатки прошлой проверки исказили бы счёт.
    await _run_tool(
        ["psql", *base, "-d", "postgres", "-c", f'DROP DATABASE IF EXISTS "{scratch}"'], env
    )
    await _run_tool(["psql", *base, "-d", "postgres", "-c", f'CREATE DATABASE "{scratch}"'], env)
    try:
        await _run_tool(
            ["pg_restore", *base, "-d", scratch, "--no-owner", "--no-privileges", str(dump_path)],
            env,
        )
        counts = []
        for table in VERIFY_TABLES:
            out = await _run_tool(
                ["psql", *base, "-d", scratch, "-t", "-A", "-c", f"SELECT count(*) FROM {table}"],
                env,
            )
            counts.append(f"{table}: {out.strip()}")
        if all(part.endswith(": 0") for part in counts):
            raise BackupError("восстановленная база пуста: " + ", ".join(counts))
        return "восстановлено — " + ", ".join(counts)
    finally:
        await _run_tool(
            ["psql", *base, "-d", "postgres", "-c", f'DROP DATABASE IF EXISTS "{scratch}"'], env
        )


# ────────────────────────────────────────────────────────────── для админки


async def history(limit: int = 50) -> list[BackupRun]:
    async with async_session_factory() as session:
        result = await session.execute(
            select(BackupRun).order_by(desc(BackupRun.started_at)).limit(limit)
        )
        return list(result.scalars())


async def summary() -> dict:
    """Сводка для панели: последние успешные копии и последняя проверка."""
    async with async_session_factory() as session:
        last: dict[str, BackupRun | None] = {}
        for kind in BackupKind:
            result = await session.execute(
                select(BackupRun)
                .where(
                    BackupRun.kind == kind,
                    BackupRun.status == BackupStatus.ok,
                    BackupRun.deleted_at.is_(None),
                )
                .order_by(desc(BackupRun.started_at))
                .limit(1)
            )
            last[kind.value] = result.scalar_one_or_none()

        verified = (
            await session.execute(
                select(BackupRun)
                .where(BackupRun.verified_at.is_not(None))
                .order_by(desc(BackupRun.verified_at))
                .limit(1)
            )
        ).scalar_one_or_none()

    def _brief(run: BackupRun | None) -> dict | None:
        if run is None:
            return None
        return {
            "id": run.id,
            "at": run.started_at,
            "size": run.size,
            "copies": run.stored_copies,
            "object_key": run.object_key,
        }

    return {
        "enabled": settings.backup_enabled,
        "hourly": _brief(last.get("hourly")),
        "daily": _brief(last.get("daily")),
        "manual": _brief(last.get("manual")),
        "retention_days": settings.backup_hourly_retention_days,
        "verify": None
        if verified is None
        else {
            "at": verified.verified_at,
            "status": verified.verify_status.value if verified.verify_status else None,
            "detail": verified.verify_detail,
        },
    }
