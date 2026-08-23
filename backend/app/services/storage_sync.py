"""Сверка и починка двух S3-бакетов.

Двойная запись при загрузке — только половина дела: зеркало могло лежать в
момент загрузки, объект мог быть удалён мимо приложения, диск провайдера мог
подвести. Поэтому есть вторая половина — регулярная сверка:

* ``verify``  — пройти по реестру и спросить каждый бакет, лежит ли объект и
  той ли он длины; расхождения записываются в реестр;
* ``repair``  — дозалить недостающие копии, взяв за образец ту, чья SHA-256
  совпадает с записанной при загрузке. Копия с другим хешем образцом быть не
  может: чинить по испорченному файлу — значит размножить порчу;
* ``purge_tombstones`` — дочистить копии удалённых файлов;
* ``scan_orphans`` — найти в бакете объекты, которых нет в реестре.

Все функции безопасны к повторному запуску и не поднимают исключений наружу:
их вызывает фоновый воркер, для которого падение задачи — это молчаливо
прекратившаяся сверка.
"""

from __future__ import annotations

import hashlib
import logging
import time

from app.models.stored_file import ReplicaState, StoredFile
from app.services import file_registry
from app.services import storage as storage_module
from app.services.s3 import S3Bucket, S3Error
from app.services.storage import ReplicatedS3Storage

logger = logging.getLogger(__name__)

OK_STATES = (ReplicaState.ok, ReplicaState.disabled)


def _replicated() -> ReplicatedS3Storage | None:
    """Хранилище в режиме двух бакетов — иначе сверять нечего.

    Читается через модуль, а не по прямой ссылке: так подмена хранилища
    (тесты, переключение режима) видна и здесь.
    """
    active = storage_module.storage
    return active if isinstance(active, ReplicatedS3Storage) else None


async def _fetch_valid(bucket: S3Bucket, row: StoredFile) -> bytes | None:
    """Скачать копию и убедиться, что это именно тот файл (по SHA-256)."""
    try:
        data = await bucket.get(row.key)
    except S3Error:
        return None
    if row.sha256 and hashlib.sha256(data).hexdigest() != row.sha256:
        logger.error(
            "контрольная сумма не совпала: %s в %s", row.key, bucket.config.name
        )
        return None
    return data


async def verify(limit: int = 500) -> dict:
    """Сверить реестр с содержимым бакетов."""
    store = _replicated()
    if store is None:
        return {"enabled": False, "checked": 0, "mismatched": 0}

    rows = await file_registry.due_for_check(limit=limit)
    checked = mismatched = 0
    for row in rows:
        states: dict[str, ReplicaState] = {}
        for bucket, field in ((store.primary, "primary"), (store.mirror, "mirror")):
            if bucket is None:
                states[field] = ReplicaState.disabled
                continue
            try:
                info = await bucket.head(row.key)
            except S3Error as exc:
                logger.warning("сверка %s в %s: %s", row.key, field, exc)
                continue
            if info is None:
                states[field] = ReplicaState.missing
                continue
            wrong_size = bool(row.size) and info.size != row.size
            wrong_hash = bool(info.sha256 and row.sha256) and info.sha256 != row.sha256
            states[field] = (
                ReplicaState.error if wrong_size or wrong_hash else ReplicaState.ok
            )

        checked += 1
        if any(state not in OK_STATES for state in states.values()):
            mismatched += 1
        await file_registry.mark_state(
            row.key,
            primary_state=states.get("primary"),
            mirror_state=states.get("mirror"),
            checked=True,
        )
    return {"enabled": True, "checked": checked, "mismatched": mismatched}


async def repair(limit: int = 100) -> dict:
    """Дозалить недостающие копии. Возвращает сводку по итогам прохода."""
    store = _replicated()
    if store is None:
        return {"enabled": False, "repaired": 0, "failed": 0, "lost": 0}

    repaired = failed = lost = 0
    for row in await file_registry.pending(limit=limit):
        targets = []
        if row.primary_state not in OK_STATES:
            targets.append(("primary", store.primary, store.mirror))
        if store.mirror is not None and row.mirror_state not in OK_STATES:
            targets.append(("mirror", store.mirror, store.primary))

        for field, target, source in targets:
            if source is None:
                continue
            data = await _fetch_valid(source, row)
            if data is None:
                # Ни одной пригодной копии — файл потерян, это тревога,
                # а не рядовое расхождение.
                lost += 1
                await file_registry.mark_state(
                    row.key,
                    **{f"{field}_state": ReplicaState.error},
                    error="нет исправной копии для восстановления",
                )
                continue
            try:
                await target.put(row.key, data, sha256=row.sha256)
            except S3Error as exc:
                failed += 1
                await file_registry.mark_state(
                    row.key, **{f"{field}_state": ReplicaState.error}, error=str(exc)
                )
                continue
            repaired += 1
            await file_registry.mark_state(
                row.key, **{f"{field}_state": ReplicaState.ok}, error="", checked=True
            )
    return {"enabled": True, "repaired": repaired, "failed": failed, "lost": lost}


async def purge_tombstones(limit: int = 100) -> dict:
    """Дочистить копии удалённых файлов и закрыть надгробия."""
    store = _replicated()
    if store is None:
        return {"enabled": False, "purged": 0, "pending": 0}

    purged = pending = 0
    for row in await file_registry.tombstones(limit=limit):
        gone = True
        for bucket in store.buckets():
            try:
                info = await bucket.head(row.key)
                if info is not None:
                    await bucket.delete(row.key)
            except S3Error as exc:
                logger.warning("уборка %s в %s: %s", row.key, bucket.config.name, exc)
                gone = False
        if gone:
            purged += 1
            await file_registry.mark_deleted(row.key, fully_removed=True)
        else:
            pending += 1
    return {"enabled": True, "purged": purged, "pending": pending}


async def scan_orphans(limit: int = 1000) -> dict:
    """Объекты в основном бакете, которых нет в реестре.

    Такие появляются после ручных операций и после миграции со старого
    диска. Автоматически ничего не удаляем — только показываем цифру.
    """
    store = _replicated()
    if store is None:
        return {"enabled": False, "orphans": 0, "sample": []}

    try:
        keys = await store.primary.list_keys(limit=limit)
    except S3Error as exc:
        return {"enabled": True, "error": str(exc), "orphans": 0, "sample": []}

    orphans = [key for key in keys if await file_registry.get(key) is None]
    return {"enabled": True, "orphans": len(orphans), "sample": orphans[:20]}


async def ping_buckets() -> list[dict]:
    """Доступность каждого бакета — для панели «Состояние системы»."""
    store = _replicated()
    if store is None:
        return []


    results = []
    for bucket in store.buckets():
        t0 = time.perf_counter()
        try:
            await bucket.ping()
            results.append(
                {
                    "name": bucket.config.name,
                    "label": bucket.config.label,
                    "status": "ok",
                    "latency_ms": round((time.perf_counter() - t0) * 1000),
                }
            )
        except S3Error as exc:
            results.append(
                {
                    "name": bucket.config.name,
                    "label": bucket.config.label,
                    "status": "down",
                    "latency_ms": round((time.perf_counter() - t0) * 1000),
                    "detail": str(exc)[:200],
                }
            )
    return results
