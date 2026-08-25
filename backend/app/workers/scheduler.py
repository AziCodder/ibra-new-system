"""Фоновый воркер: бэкапы по расписанию и сверка двух S3.

Запускается отдельным процессом (контейнер ``worker``) из того же образа:

    python -m app.workers.scheduler

**Почему задачи не выполняет сам API.** Воркер поднимается на обоих серверах
кластера, но работать должен только тот, который сейчас главный. Признак
берётся у самой базы: ``pg_is_in_recovery()`` возвращает ``true`` на реплике.
Резерв читает этот флаг и молча пропускает задачу — двух одновременных
бэкапов и двух конкурирующих починок хранилища не бывает по построению, без
отдельного координатора. После переключения новый главный начинает
выполнять задачи сам, потому что его база перестала быть репликой.

Расписание (время — из ``BACKUP_TIMEZONE``):

* каждый час, :05          — часовая копия (хранится 7 дней);
* ежедневно 03:15          — суточная копия (постоянная);
* ежедневно 04:00          — чистка часовых копий по сроку хранения;
* ежедневно 04:30          — проверка последней суточной копии восстановлением;
* каждые 15 минут          — сверка и починка двух бакетов.

Отдельно стоят два сторожа кластера — они работают на ОБОИХ узлах, потому
что именно резерв должен заметить смерть главного:

* каждые 30 секунд — наблюдение за соседом (перехват работы при аварии);
* каждые 30 секунд — надзор за репликой. В синхронном режиме: уход в
  асинхронный, если реплика пропала, и возврат, когда она вернулась.
  В асинхронном (серверы в разных странах): измерение отставания — это и
  есть размер возможной потери — и тревога, когда порог превышен.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import text

from app.core.config import settings
from app.core.database import async_session_factory, engine
from app.core.logging_config import setup_logging
from app.models.backup_run import BackupKind
from app.services import backup, failover, storage_sync

logger = logging.getLogger("worker")


async def is_primary() -> bool:
    """Мы на главном узле? На реплике база отвечает, что она в восстановлении."""
    try:
        async with async_session_factory() as session:
            result = await session.execute(text("SELECT pg_is_in_recovery()"))
            return not bool(result.scalar())
    except Exception as exc:  # noqa: BLE001 — воркер не должен падать из-за проверки
        logger.warning("не удалось определить роль узла: %s", exc)
        return False


def guarded(name: str, func, *, quiet: bool = False):
    """Обёртка: задача не роняет воркер, что бы внутри ни случилось."""

    async def runner() -> None:
        if not quiet:
            logger.info("задача %s: старт", name)
        try:
            result = await func()
            logger.log(
                logging.DEBUG if quiet else logging.INFO, "задача %s: готово — %s", name, result
            )
        except Exception:  # noqa: BLE001 — иначе один сбой убивает всё расписание
            logger.exception("задача %s: сбой", name)

    runner.__name__ = f"job_{name}"
    return runner


def only_on_primary(name: str, func):
    """Обёртка: задача выполняется лишь на главном узле."""

    async def guard():
        if not await is_primary():
            logger.debug("задача %s пропущена: узел в резерве", name)
            return "пропущено: узел в резерве"
        return await func()

    return guarded(name, guard)


async def sync_storage() -> dict:
    """Сверка бакетов и починка расхождений одним проходом."""
    verified = await storage_sync.verify()
    repaired = await storage_sync.repair()
    purged = await storage_sync.purge_tombstones()
    return {"verify": verified, "repair": repaired, "purge": purged}


def build_scheduler() -> AsyncIOScheduler:
    tz = ZoneInfo(settings.backup_timezone)
    scheduler = AsyncIOScheduler(
        timezone=tz,
        job_defaults={
            # Пропущенный из-за перезапуска прогон не должен запускаться
            # пачкой, а затянувшийся — накладываться сам на себя.
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 3600,
        },
    )

    if settings.backup_enabled:
        scheduler.add_job(
            only_on_primary("hourly_backup", lambda: backup.create(BackupKind.hourly)),
            CronTrigger(minute=settings.backup_hourly_minute, timezone=tz),
            id="hourly_backup",
        )
        scheduler.add_job(
            only_on_primary("daily_backup", lambda: backup.create(BackupKind.daily)),
            CronTrigger(
                hour=settings.backup_daily_hour,
                minute=settings.backup_daily_minute,
                timezone=tz,
            ),
            id="daily_backup",
        )
        scheduler.add_job(
            only_on_primary("backup_cleanup", backup.cleanup),
            CronTrigger(hour=4, minute=0, timezone=tz),
            id="backup_cleanup",
        )
        if settings.backup_verify_enabled:
            scheduler.add_job(
                only_on_primary("backup_verify", backup.verify_last),
                CronTrigger(hour=4, minute=30, timezone=tz),
                id="backup_verify",
            )

    scheduler.add_job(
        only_on_primary("storage_sync", sync_storage),
        IntervalTrigger(minutes=settings.storage_sync_interval_minutes, timezone=tz),
        id="storage_sync",
    )

    # Сторожа кластера — единственные задачи, которые обязаны работать и на
    # резерве: именно резерв замечает смерть главного и перехватывает работу.
    if settings.peer_url:
        scheduler.add_job(
            guarded("peer_watch", failover.watch_peer),
            IntervalTrigger(seconds=30, timezone=tz),
            id="peer_watch",
        )
    if settings.sync_replication:
        scheduler.add_job(
            guarded("replication_guard", failover.guard_replication),
            IntervalTrigger(seconds=30, timezone=tz),
            id="replication_guard",
        )
    return scheduler


async def main() -> None:
    setup_logging(production=settings.is_production)
    scheduler = build_scheduler()
    scheduler.start()
    logger.info(
        "воркер запущен (%s), задач: %s",
        settings.backup_timezone,
        ", ".join(job.id for job in scheduler.get_jobs()),
    )

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        # На Windows обработчиков сигналов у цикла событий нет — воркер
        # там и не живёт, но падать из-за этого при локальном запуске незачем.
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)

    try:
        await stop.wait()
    finally:
        scheduler.shutdown(wait=True)
        await engine.dispose()
        logger.info("воркер остановлен")


if __name__ == "__main__":
    asyncio.run(main())
