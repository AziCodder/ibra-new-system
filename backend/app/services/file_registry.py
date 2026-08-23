"""Учёт файлов во внешнем хранилище: кто где лежит и что отстало.

Реестр ведётся в своей транзакции (собственная сессия), а не в сессии
запроса. Это осознанно: если запрос упадёт уже после заливки файла, объект
в бакете всё равно остался — и он должен остаться видимым для сверки и
уборки, а не превратиться в невидимый мусор из-за отката транзакции.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, or_, select

from app.core.database import async_session_factory
from app.models.stored_file import ReplicaState, StoredFile


def _now() -> datetime:
    return datetime.now(UTC)


async def record_saved(
    key: str,
    *,
    filename: str,
    size: int,
    sha256: str,
    primary_state: ReplicaState,
    mirror_state: ReplicaState,
    error: str = "",
) -> None:
    """Записать (или обновить) состояние файла сразу после загрузки."""
    async with async_session_factory() as session:
        row = await session.get(StoredFile, key)
        if row is None:
            row = StoredFile(key=key)
            session.add(row)
        row.filename = filename
        row.size = size
        row.sha256 = sha256
        row.primary_state = primary_state
        row.mirror_state = mirror_state
        row.last_error = error[:1000]
        row.deleted_at = None
        if primary_state == ReplicaState.ok and mirror_state in (
            ReplicaState.ok,
            ReplicaState.disabled,
        ):
            row.replicated_at = _now()
        await session.commit()


async def mark_state(
    key: str,
    *,
    primary_state: ReplicaState | None = None,
    mirror_state: ReplicaState | None = None,
    error: str | None = None,
    checked: bool = False,
) -> None:
    """Точечно обновить состояние копий (сверка, дозаливка, починка)."""
    async with async_session_factory() as session:
        row = await session.get(StoredFile, key)
        if row is None:
            return
        if primary_state is not None:
            row.primary_state = primary_state
        if mirror_state is not None:
            row.mirror_state = mirror_state
        if error is not None:
            row.last_error = error[:1000]
        if checked:
            row.checked_at = _now()
        if row.primary_state == ReplicaState.ok and row.mirror_state in (
            ReplicaState.ok,
            ReplicaState.disabled,
        ):
            row.replicated_at = _now()
        await session.commit()


async def mark_deleted(key: str, *, fully_removed: bool) -> None:
    """Пометить файл удалённым.

    ``fully_removed`` — удаление подтвердили оба бакета: строку можно убрать.
    Иначе остаётся надгробие, и фоновая задача дочистит отставшую копию.
    """
    async with async_session_factory() as session:
        row = await session.get(StoredFile, key)
        if row is None:
            return
        if fully_removed:
            await session.delete(row)
        else:
            row.deleted_at = _now()
        await session.commit()


async def get(key: str) -> StoredFile | None:
    async with async_session_factory() as session:
        return await session.get(StoredFile, key)


async def pending(limit: int = 200) -> list[StoredFile]:
    """Файлы, у которых хотя бы одна копия не в порядке, — работа для воркера."""
    bad = (ReplicaState.pending, ReplicaState.error, ReplicaState.missing)
    async with async_session_factory() as session:
        result = await session.execute(
            select(StoredFile)
            .where(
                StoredFile.deleted_at.is_(None),
                or_(StoredFile.primary_state.in_(bad), StoredFile.mirror_state.in_(bad)),
            )
            .order_by(StoredFile.created_at)
            .limit(limit)
        )
        return list(result.scalars())


async def tombstones(limit: int = 200) -> list[StoredFile]:
    """Удалённые файлы, у которых копия где-то ещё осталась."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(StoredFile)
            .where(StoredFile.deleted_at.is_not(None))
            .order_by(StoredFile.deleted_at)
            .limit(limit)
        )
        return list(result.scalars())


async def summary() -> dict:
    """Сводка для админки: сколько файлов, сколько байт, сколько разъехалось."""
    ok_states = (ReplicaState.ok, ReplicaState.disabled)
    async with async_session_factory() as session:
        total, total_size = (
            await session.execute(
                select(func.count(), func.coalesce(func.sum(StoredFile.size), 0)).where(
                    StoredFile.deleted_at.is_(None)
                )
            )
        ).one()
        out_of_sync = (
            await session.execute(
                select(func.count()).where(
                    StoredFile.deleted_at.is_(None),
                    or_(
                        StoredFile.primary_state.not_in(ok_states),
                        StoredFile.mirror_state.not_in(ok_states),
                    ),
                )
            )
        ).scalar_one()
        pending_deletes = (
            await session.execute(
                select(func.count()).where(StoredFile.deleted_at.is_not(None))
            )
        ).scalar_one()
        last_check = (
            await session.execute(select(func.max(StoredFile.checked_at)))
        ).scalar_one()

    return {
        "files": int(total),
        "bytes": int(total_size),
        "out_of_sync": int(out_of_sync),
        "pending_deletes": int(pending_deletes),
        "last_check": last_check,
    }
