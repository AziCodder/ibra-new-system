"""Автоматический перехват работы вторым сервером.

Два узла — это не кворум: голосовать некому, и каждый видит только себя и
соседа. Отсюда все решения ниже.

**Резерв перехватывает работу, только если совпало всё:**

1. перехват вообще разрешён настройкой (``FAILOVER_ENABLED``);
2. мы действительно резерв (у базы спросили, а не в конфиге прочитали);
3. сосед не отвечает N проверок подряд, а не одну — моргнувшая сеть не
   повод менять главного;
4. у нас самих есть связь с внешним миром. Если внешние точки тоже молчат,
   значит сеть потеряли МЫ. Перехват в этот момент дал бы двух «главных» и
   разъехавшиеся данные — худший исход из возможных.

**Главный, оставшийся в одиночестве, сам себя ограничивает.** Если он не
видит ни соседа, ни внешнего мира, он переходит в режим «только чтение»:
раз домен уже могли увести на второй сервер, продолжать принимать запись
опасно — эти записи потом некуда будет девать.

**Обратно всё возвращается вручную.** Автоматический возврат на исходный
сервер устроил бы «пинг-понг» при мигающей сети, а каждое переключение —
это разрыв соединений и секунды простоя.
"""

from __future__ import annotations

import logging

from app.core.config import settings
from app.services import cluster, dns_failover, telegram_bot

logger = logging.getLogger(__name__)


class _State:
    """Счётчики живут в памяти воркера — процесс долгоживущий."""

    peer_failures = 0
    isolated_checks = 0
    standby_missing_since: float | None = None
    failed_over = False


state = _State()


async def watch_peer() -> dict:
    """Резерв следит за главным. Задача воркера, раз в полминуты."""
    if not settings.peer_url:
        return {"checked": False, "detail": "адрес соседа не задан"}

    role = await cluster.role()
    peer = await cluster.peer()

    if peer and peer["alive"]:
        if state.peer_failures:
            logger.info("сосед снова отвечает после %d неудачных проверок", state.peer_failures)
        state.peer_failures = 0
        return {"checked": True, "role": role, "peer_alive": True}

    state.peer_failures += 1
    logger.warning(
        "сосед не отвечает (%d/%d): %s",
        state.peer_failures,
        settings.peer_failures_before_failover,
        (peer or {}).get("detail", ""),
    )

    if role == cluster.PRIMARY:
        # Главный: сосед мёртв — значит синхронной репликации больше нет.
        # Этим занимается replication_guard, здесь только самопроверка на
        # изоляцию, чтобы не писать данные в никуда.
        return await _guard_isolation()

    if not settings.failover_enabled:
        return {"checked": True, "role": role, "peer_alive": False, "detail": "перехват выключен"}

    if state.peer_failures < settings.peer_failures_before_failover:
        return {"checked": True, "role": role, "peer_alive": False, "failures": state.peer_failures}

    if not await cluster.have_internet():
        logger.error("сосед недоступен, но и внешний мир тоже — перехват отменён, проблема у нас")
        state.peer_failures = 0
        return {"checked": True, "role": role, "peer_alive": False, "detail": "нет связи у нас самих"}

    return await take_over()


async def take_over() -> dict:
    """Стать главным: повысить реплику и перевести домен на себя."""
    if state.failed_over:
        return {"detail": "перехват уже выполнен"}

    logger.error("ПЕРЕХВАТ: главный сервер не отвечает, поднимаю себя")
    promoted = await cluster.promote()
    dns = await dns_failover.point_domain_to(settings.node_public_ip)
    state.failed_over = True
    state.peer_failures = 0

    text = (
        f"⚠️ Автоматическое переключение на резервный сервер ({settings.node_name}).\n"
        f"База повышена до главной: {'да' if promoted else 'НЕТ — требуется вмешательство'}.\n"
        f"Домен {dns_failover.fqdn()}: "
        + ("переведён на " + settings.node_public_ip if dns.get("changed") else f"НЕ переведён — {dns.get('detail')}")
        + "\n\nВозврат на исходный сервер выполняется вручную."
    )
    await _notify(text)
    return {"promoted": promoted, "dns": dns, "took_over": True}


async def _guard_isolation() -> dict:
    """Главный проверяет, не остался ли он один в отрезанной сети."""
    if await cluster.have_internet():
        state.isolated_checks = 0
        return {"checked": True, "role": cluster.PRIMARY, "peer_alive": False, "isolated": False}

    state.isolated_checks += 1
    if state.isolated_checks < settings.peer_failures_before_failover:
        return {"checked": True, "role": cluster.PRIMARY, "isolated": "подозрение"}

    if not await cluster.read_only():
        logger.error("узел изолирован: ни соседа, ни внешней сети — перехожу в режим только чтения")
        await cluster.set_read_only(True)
        await _notify(
            f"⚠️ Сервер {settings.node_name} потерял связь с сетью и переведён в режим только чтения, "
            "чтобы данные не разошлись со вторым сервером. Требуется вмешательство."
        )
    return {"checked": True, "role": cluster.PRIMARY, "isolated": True}


async def guard_replication() -> dict:
    """Главный следит за синхронной репликой.

    Синхронный режим означает «подтверждать транзакцию только после записи
    на второй сервер». Если второй сервер умер, каждая запись будет ждать
    его вечно — то есть система встанет целиком. Поэтому при пропаже реплики
    режим сам опускается до асинхронного, а как только реплика вернётся —
    поднимается обратно.
    """
    import time

    if await cluster.role() != cluster.PRIMARY or not settings.sync_replication:
        return {"applicable": False}

    connected = [r for r in await cluster.replicas() if r["state"] == "streaming"]
    sync_on = bool(await cluster.sync_standby_names())

    if connected:
        state.standby_missing_since = None
        if not sync_on:
            await cluster.set_sync(True)
            await _notify(
                f"Реплика вернулась — синхронная репликация на {settings.node_name} снова включена."
            )
            return {"applicable": True, "action": "sync_restored"}
        return {"applicable": True, "action": "ok", "replicas": len(connected)}

    if not sync_on:
        return {"applicable": True, "action": "already_degraded"}

    now = time.monotonic()
    if state.standby_missing_since is None:
        state.standby_missing_since = now
        return {"applicable": True, "action": "standby_missing"}

    if now - state.standby_missing_since < settings.sync_degrade_after_seconds:
        return {"applicable": True, "action": "waiting"}

    await cluster.set_sync(False)
    await _notify(
        f"⚠️ Реплика недоступна дольше {settings.sync_degrade_after_seconds} c. "
        f"Сервер {settings.node_name} переведён в асинхронный режим, чтобы не остановить работу. "
        "Данные сейчас пишутся только на один сервер — почините резерв."
    )
    return {"applicable": True, "action": "degraded"}


async def _notify(message: str) -> None:
    """Сообщить людям. Тревога о кластере не должна теряться в логах."""
    logger.warning("тревога кластера: %s", message.replace("\n", " "))
    if not settings.alert_chat_id:
        return
    try:
        await telegram_bot.send_message(settings.alert_chat_id, message)
    except Exception:  # noqa: BLE001 — сбой уведомления не должен ломать переключение
        logger.exception("не удалось отправить уведомление о состоянии кластера")
