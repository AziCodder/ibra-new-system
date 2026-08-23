"""Перенос вложений со старого диска в S3 (оба бакета сразу).

Разовая операция при переезде на новую инфраструктуру: файлы, лежащие в
``UPLOAD_DIR``, заливаются в основной бакет и в зеркало, после чего попадают
в реестр ``stored_files`` с посчитанной SHA-256.

    python -m app.scripts.migrate_files_to_s3            # перенести
    python -m app.scripts.migrate_files_to_s3 --dry-run  # только посмотреть

Ключи файлов не меняются — они уже проставлены в заказах, заявках и товарах,
и переименование разорвало бы все ссылки. Исходные файлы на диске скрипт не
трогает: удалять их можно только после сверки (`storage_sync.verify`).
Скрипт можно запускать повторно — уже перенесённые файлы пропускаются.
"""

from __future__ import annotations

import asyncio
import hashlib
import mimetypes
import sys
from pathlib import Path

from app.core.config import settings
from app.models.stored_file import ReplicaState
from app.services import file_registry
from app.services.s3 import S3Error
from app.services.storage import ReplicatedS3Storage, build_storage


async def migrate(*, dry_run: bool = False) -> dict:
    store = build_storage()
    if not isinstance(store, ReplicatedS3Storage):
        raise SystemExit(
            "STORAGE_BACKEND=s3 не включён — переносить некуда. "
            "Заполните реквизиты бакетов и повторите."
        )

    source = Path(settings.upload_dir)
    if not source.exists():
        raise SystemExit(f"Папка {source} не найдена")

    stats = {"total": 0, "uploaded": 0, "skipped": 0, "failed": 0}
    failures: list[str] = []

    for path in sorted(source.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        stats["total"] += 1
        key = path.name

        existing = await file_registry.get(key)
        if existing is not None and existing.in_sync:
            stats["skipped"] += 1
            continue

        data = path.read_bytes()
        sha256 = hashlib.sha256(data).hexdigest()
        content_type = mimetypes.guess_type(key)[0]

        if dry_run:
            stats["uploaded"] += 1
            print(f"[dry-run] {key} — {len(data)} байт")
            continue

        try:
            await store.primary.put(key, data, sha256=sha256, content_type=content_type)
        except S3Error as exc:
            stats["failed"] += 1
            failures.append(f"{key}: основной бакет — {exc}")
            continue

        mirror_state = ReplicaState.disabled
        error = ""
        if store.mirror is not None:
            try:
                await store.mirror.put(key, data, sha256=sha256, content_type=content_type)
                mirror_state = ReplicaState.ok
            except S3Error as exc:
                mirror_state = ReplicaState.error
                error = str(exc)
                failures.append(f"{key}: зеркало — {exc}")

        await file_registry.record_saved(
            key,
            filename=key,
            size=len(data),
            sha256=sha256,
            primary_state=ReplicaState.ok,
            mirror_state=mirror_state,
            error=error,
        )
        stats["uploaded"] += 1

    print(
        f"Файлов найдено: {stats['total']}, перенесено: {stats['uploaded']}, "
        f"пропущено (уже в S3): {stats['skipped']}, с ошибками: {stats['failed']}"
    )
    if failures:
        print("\nОшибки:")
        for line in failures[:50]:
            print(f"  - {line}")
    if stats["failed"] == 0 and not dry_run:
        print(
            "\nИсходные файлы на диске оставлены как есть. Удалять их можно "
            "только после сверки бакетов."
        )
    return stats


if __name__ == "__main__":
    asyncio.run(migrate(dry_run="--dry-run" in sys.argv))
