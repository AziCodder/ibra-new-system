"""Управление резервными копиями из админки.

Долгие операции (снятие копии, откат) запускаются фоновой задачей: pg_dump
большой базы идёт минутами, и держать ради него HTTP-запрос нельзя. Клиент
видит появившуюся строку со статусом ``running`` и обновляет список.

Все три действия пишутся в журнал действий: и создание, и удаление копии, и
особенно откат — операцию, после которой данные системы становятся другими.
"""

from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.models.backup_run import BackupKind, BackupRun
from app.models.stored_file import ReplicaState
from app.models.user import User, UserRole
from app.routers.auth import require_role
from app.schemas.backups import (
    BackupActionOut,
    BackupCreateIn,
    BackupListOut,
)
from app.services import backup
from app.services.action_log import log_action

router = APIRouter(prefix="/api/backups", tags=["backups"])


def _serialize(run: BackupRun) -> dict:
    # Часовая копия живёт ограниченный срок — показываем, до какого момента.
    expires_at = (
        run.started_at + timedelta(days=settings.backup_hourly_retention_days)
        if run.kind == BackupKind.hourly
        else None
    )
    return {
        "id": run.id,
        "kind": run.kind.value,
        "label": run.label,
        "title": run.title,
        "permanent": run.permanent,
        "status": run.status.value,
        "object_key": run.object_key,
        "size": run.size,
        "sha256": run.sha256,
        "copies": run.stored_copies,
        "primary_state": run.primary_state.value,
        "mirror_state": run.mirror_state.value,
        "stored_locally": bool(run.local_path),
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "duration_ms": run.duration_ms,
        "error": run.error,
        "node": run.node,
        "verified_at": run.verified_at,
        "verify_status": run.verify_status.value if run.verify_status else None,
        "verify_detail": run.verify_detail,
        "restored_at": run.restored_at,
        "restore_status": run.restore_status.value if run.restore_status else None,
        "restore_detail": run.restore_detail,
        "expires_at": expires_at,
        "stalled": backup.is_stalled(run),
    }


@router.get("/", response_model=BackupListOut)
async def list_backups(
    _admin: User = require_role(UserRole.admin),
) -> dict:
    summary = await backup.summary()
    buckets = backup.backup_buckets()
    summary["storage"] = (
        f"{len(buckets)} S3-хранилищ" if buckets else "только диск сервера (S3 не настроен)"
    )
    return {"summary": summary, "items": [_serialize(run) for run in await backup.history()]}


@router.post("/", response_model=BackupActionOut)
async def create_backup(
    payload: BackupCreateIn,
    background: BackgroundTasks,
    admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Снять копию вручную. Ручные копии постоянные — сроком хранения не чистятся."""
    if not settings.backup_enabled:
        raise HTTPException(status_code=400, detail="Резервное копирование отключено настройкой")

    name = payload.name.strip()
    await log_action(session, admin, "backup_create", "backup", 0, name or "без имени")
    await session.commit()

    background.add_task(backup.create, BackupKind.manual, name)
    return {"status": "started", "title": name}


@router.delete("/{run_id}", response_model=BackupActionOut)
async def delete_backup(
    run_id: int,
    admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await backup.remove(run_id)
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail="Копия не найдена")
    if result["status"] == "busy":
        raise HTTPException(status_code=409, detail=result["detail"])
    if result["status"] == "failed":
        raise HTTPException(status_code=502, detail=f"Хранилище не подтвердило удаление: {result['detail']}")

    await log_action(session, admin, "backup_delete", "backup", run_id, result.get("title", ""))
    await session.commit()
    return result


@router.post("/{run_id}/restore", response_model=BackupActionOut)
async def restore_backup(
    run_id: int,
    background: BackgroundTasks,
    admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Откатить базу на выбранную копию.

    Перед откатом система сама снимает страховочную копию текущего состояния,
    а прежняя база сохраняется рядом — ошибочный откат обратим.
    """
    run = await session.get(BackupRun, run_id)
    if run is None or run.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Копия не найдена")
    if run.status.value != "ok":
        raise HTTPException(status_code=409, detail="Копия снята с ошибкой, откат невозможен")
    if run.primary_state == ReplicaState.disabled and not run.local_path:
        raise HTTPException(status_code=409, detail="Файл копии недоступен")

    await log_action(session, admin, "backup_restore", "backup", run_id, run.title)
    await session.commit()

    background.add_task(backup.restore, run_id)
    return {"status": "started", "id": run_id, "title": run.title}
