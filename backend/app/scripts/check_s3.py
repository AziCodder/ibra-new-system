"""Проверить связь с обоими S3-хранилищами до того, как на них переедут файлы.

    python -m app.scripts.check_s3

Скрипт не верит настройкам на слово: он реально записывает пробный объект,
читает его обратно, сверяет содержимое и удаляет. Живой ответ на «ping»
ничего не доказывает — доступ может быть только на чтение, бакет может не
существовать, ключ может не иметь прав на удаление. Всё это выяснится
позже и в худший момент, если не проверить сейчас.
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid

from app.core.config import settings
from app.services.s3 import S3Bucket, S3Error

PROBE = b"ibra storage probe"


async def check(bucket: S3Bucket) -> list[str]:
    """Полный цикл записи-чтения-удаления. Возвращает список ошибок."""
    label = bucket.config.label
    key = f".probe/{uuid.uuid4().hex}.txt"
    sha = hashlib.sha256(PROBE).hexdigest()
    problems: list[str] = []

    try:
        await bucket.ping()
        print(f"  [{label}] бакет доступен")
    except S3Error as exc:
        return [f"{label}: бакет недоступен — {exc}"]

    try:
        await bucket.put(key, PROBE, sha256=sha, content_type="text/plain")
        print(f"  [{label}] запись — ок")
    except S3Error as exc:
        return [f"{label}: нет прав на запись — {exc}"]

    try:
        data = await bucket.get(key)
        if data != PROBE:
            problems.append(f"{label}: прочитано не то, что записано")
        else:
            print(f"  [{label}] чтение — ок")
    except S3Error as exc:
        problems.append(f"{label}: нет прав на чтение — {exc}")

    try:
        info = await bucket.head(key)
        if info is None:
            problems.append(f"{label}: объект не виден в HEAD — сверка бакетов работать не будет")
        elif info.sha256 != sha:
            problems.append(
                f"{label}: провайдер не сохраняет метаданные объекта — "
                "сверка по контрольной сумме работать не будет"
            )
        else:
            print(f"  [{label}] метаданные (SHA-256) — ок")
    except S3Error as exc:
        problems.append(f"{label}: HEAD не работает — {exc}")

    try:
        await bucket.delete(key)
        print(f"  [{label}] удаление — ок")
    except S3Error as exc:
        problems.append(f"{label}: нет прав на удаление — {exc} (пробный объект остался: {key})")

    return problems


async def main() -> int:
    if settings.storage_backend != "s3":
        print("STORAGE_BACKEND не равен 's3' — проверять нечего.")
        return 1

    configured = [
        ("основное", settings.s3_primary_config),
        ("зеркало", settings.s3_mirror_config),
    ]
    problems: list[str] = []
    for role, config in configured:
        print(f"\n{role.upper()}: {config.label} ({config.bucket} @ {config.endpoint_url or 'не задан'})")
        if not config.configured:
            message = f"{role}: реквизиты не заполнены"
            if role == "зеркало":
                print("  пропускаю: зеркало не настроено — отказоустойчивости хранилища НЕТ")
                problems.append(message + " — файлы будут храниться в одном месте")
            else:
                problems.append(message)
            continue
        problems.extend(await check(S3Bucket(config)))

    print("\n" + "─" * 60)
    if problems:
        print("Есть проблемы:")
        for line in problems:
            print(f"  ✗ {line}")
        return 1
    print("Оба хранилища готовы: запись, чтение, метаданные и удаление работают.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
