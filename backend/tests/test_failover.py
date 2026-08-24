"""Перехват работы вторым сервером: когда переключаться, а когда — ни в коем случае.

Здесь проверяется логика решений, а не сам PostgreSQL: повышение реплики и
переключение DNS подменены. Цена ошибки в этой логике — два «главных» узла
и разъехавшиеся данные, поэтому запретов в тестах больше, чем разрешений.
"""

import pytest

from app.core.config import settings
from app.services import cluster, dns_failover, failover


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    failover.state.peer_failures = 0
    failover.state.isolated_checks = 0
    failover.state.standby_missing_since = None
    failover.state.failed_over = False
    monkeypatch.setattr(settings, "peer_url", "https://10.0.0.2/api/cluster/ping")
    monkeypatch.setattr(settings, "failover_enabled", True)
    monkeypatch.setattr(settings, "node_public_ip", "10.0.0.2")
    monkeypatch.setattr(settings, "peer_failures_before_failover", 3)
    monkeypatch.setattr(settings, "alert_chat_id", "")
    yield


def _stub(monkeypatch, **values):
    """Подменить функции модуля cluster заранее заданными ответами."""
    async def make(value):
        return value

    for name, value in values.items():
        monkeypatch.setattr(cluster, name, lambda *a, _v=value, **kw: make(_v))


@pytest.fixture
def promoted(monkeypatch):
    calls = []

    async def _promote(*args, **kwargs):
        calls.append("promote")
        return True

    async def _dns(ip):
        calls.append(f"dns:{ip}")
        return {"provider": "test", "changed": True, "ip": ip}

    monkeypatch.setattr(cluster, "promote", _promote)
    monkeypatch.setattr(dns_failover, "point_domain_to", _dns)
    return calls


# ── когда перехватывать НЕЛЬЗЯ ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_single_missed_check_is_not_a_failover(monkeypatch, promoted):
    """Одна осечка — это моргнувшая сеть, а не смерть сервера."""
    _stub(monkeypatch, role=cluster.STANDBY, peer={"alive": False}, have_internet=True)

    result = await failover.watch_peer()

    assert result["failures"] == 1
    assert promoted == []


@pytest.mark.asyncio
async def test_no_failover_when_we_are_the_one_without_network(monkeypatch, promoted):
    """Сосед молчит и внешний мир молчит — значит сеть потеряли мы сами.

    Перехват в этот момент дал бы двух «главных» — это худший исход.
    """
    _stub(monkeypatch, role=cluster.STANDBY, peer={"alive": False}, have_internet=False)

    results = [await failover.watch_peer() for _ in range(5)]

    assert promoted == []
    assert any("нет связи у нас самих" in r.get("detail", "") for r in results)


@pytest.mark.asyncio
async def test_no_failover_while_the_switch_is_off(monkeypatch, promoted):
    monkeypatch.setattr(settings, "failover_enabled", False)
    _stub(monkeypatch, role=cluster.STANDBY, peer={"alive": False}, have_internet=True)

    for _ in range(5):
        await failover.watch_peer()

    assert promoted == []


@pytest.mark.asyncio
async def test_primary_never_takes_over_itself(monkeypatch, promoted):
    """Мы уже главный — перехватывать не у кого."""
    _stub(monkeypatch, role=cluster.PRIMARY, peer={"alive": False}, have_internet=True, read_only=False)

    for _ in range(5):
        await failover.watch_peer()

    assert promoted == []


@pytest.mark.asyncio
async def test_recovered_peer_resets_the_counter(monkeypatch, promoted):
    """Сосед ответил — счётчик обнуляется, иначе редкие осечки накопились бы
    за неделю и однажды устроили переключение на ровном месте."""
    _stub(monkeypatch, role=cluster.STANDBY, peer={"alive": False}, have_internet=True)
    await failover.watch_peer()
    await failover.watch_peer()
    assert failover.state.peer_failures == 2

    _stub(monkeypatch, role=cluster.STANDBY, peer={"alive": True}, have_internet=True)
    await failover.watch_peer()

    assert failover.state.peer_failures == 0
    assert promoted == []


# ── когда перехватывать НУЖНО ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_failover_after_enough_failures(monkeypatch, promoted):
    _stub(monkeypatch, role=cluster.STANDBY, peer={"alive": False}, have_internet=True)

    for _ in range(settings.peer_failures_before_failover):
        result = await failover.watch_peer()

    assert result["took_over"] is True
    assert promoted == ["promote", "dns:10.0.0.2"]
    assert failover.state.failed_over is True


@pytest.mark.asyncio
async def test_failover_happens_once(monkeypatch, promoted):
    """Повторные срабатывания не должны дёргать DNS снова и снова."""
    _stub(monkeypatch, role=cluster.STANDBY, peer={"alive": False}, have_internet=True)
    for _ in range(settings.peer_failures_before_failover * 2):
        await failover.watch_peer()

    assert promoted.count("promote") == 1


# ── самоограждение главного ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_isolated_primary_goes_read_only(monkeypatch):
    """Главный без сети и без соседа обязан перестать принимать запись."""
    switched = []

    async def _set_read_only(enabled):
        switched.append(enabled)

    _stub(monkeypatch, role=cluster.PRIMARY, peer={"alive": False}, have_internet=False, read_only=False)
    monkeypatch.setattr(cluster, "set_read_only", _set_read_only)

    for _ in range(settings.peer_failures_before_failover):
        result = await failover.watch_peer()

    assert result["isolated"] is True
    assert switched == [True]


@pytest.mark.asyncio
async def test_primary_with_internet_keeps_writing(monkeypatch):
    """Сосед умер, но сеть на месте — работу останавливать незачем."""
    switched = []

    async def _set_read_only(enabled):
        switched.append(enabled)

    _stub(monkeypatch, role=cluster.PRIMARY, peer={"alive": False}, have_internet=True, read_only=False)
    monkeypatch.setattr(cluster, "set_read_only", _set_read_only)

    for _ in range(5):
        result = await failover.watch_peer()

    assert result["isolated"] is False
    assert switched == []


# ── синхронная реплика ─────────────────────────────────────────────────────


@pytest.fixture
def sync_switch(monkeypatch):
    calls = []

    async def _set_sync(enabled):
        calls.append(enabled)
        return "ANY 1 (standby)" if enabled else ""

    monkeypatch.setattr(cluster, "set_sync", _set_sync)
    monkeypatch.setattr(settings, "sync_replication", True)
    monkeypatch.setattr(settings, "sync_degrade_after_seconds", 0)
    return calls


@pytest.mark.asyncio
async def test_healthy_replica_keeps_sync_on(monkeypatch, sync_switch):
    _stub(
        monkeypatch,
        role=cluster.PRIMARY,
        replicas=[{"state": "streaming", "sync_state": "sync"}],
        sync_standby_names="ANY 1 (standby)",
    )

    result = await failover.guard_replication()

    assert result["action"] == "ok"
    assert sync_switch == []


@pytest.mark.asyncio
async def test_missing_replica_degrades_to_async(monkeypatch, sync_switch):
    """Синхронный режим с мёртвой репликой заморозил бы запись целиком."""
    _stub(monkeypatch, role=cluster.PRIMARY, replicas=[], sync_standby_names="ANY 1 (standby)")

    first = await failover.guard_replication()
    second = await failover.guard_replication()

    assert first["action"] == "standby_missing"  # сначала засекаем время
    assert second["action"] == "degraded"
    assert sync_switch == [False]


@pytest.mark.asyncio
async def test_returned_replica_restores_sync(monkeypatch, sync_switch):
    """Реплика вернулась — синхронный режим обязан включиться сам."""
    _stub(monkeypatch, role=cluster.PRIMARY, replicas=[{"state": "streaming", "sync_state": "async"}],
          sync_standby_names="")

    result = await failover.guard_replication()

    assert result["action"] == "sync_restored"
    assert sync_switch == [True]


@pytest.mark.asyncio
async def test_replication_guard_is_idle_on_standby(monkeypatch, sync_switch):
    _stub(monkeypatch, role=cluster.STANDBY)

    assert (await failover.guard_replication())["applicable"] is False
    assert sync_switch == []


# ── переключение домена ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_manual_dns_mode_changes_nothing(monkeypatch):
    monkeypatch.setattr(settings, "dns_provider", "none")

    result = await dns_failover.point_domain_to("10.0.0.2")

    assert result["changed"] is False
    assert "ручной режим" in result["detail"]


@pytest.mark.asyncio
async def test_dns_switch_without_ip_is_refused(monkeypatch):
    monkeypatch.setattr(settings, "dns_provider", "cloudflare")

    result = await dns_failover.point_domain_to("")

    assert result["changed"] is False
    assert "NODE_PUBLIC_IP" in result["detail"]


@pytest.mark.asyncio
async def test_missing_dns_credentials_are_reported_not_swallowed(monkeypatch):
    monkeypatch.setattr(settings, "dns_provider", "cloudflare")
    monkeypatch.setattr(settings, "cloudflare_api_token", "")

    result = await dns_failover.point_domain_to("10.0.0.2")

    assert result["changed"] is False
    assert "CLOUDFLARE_API_TOKEN" in result["detail"]


def test_fqdn_is_built_from_zone_and_record(monkeypatch):
    monkeypatch.setattr(settings, "dns_zone", "cargo-ibragim.ru")
    monkeypatch.setattr(settings, "dns_record", "flow")
    assert dns_failover.fqdn() == "flow.cargo-ibragim.ru"

    monkeypatch.setattr(settings, "dns_record", "@")
    assert dns_failover.fqdn() == "cargo-ibragim.ru"
