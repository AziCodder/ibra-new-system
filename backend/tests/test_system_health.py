"""Состояние системы: что именно видно в админке.

Проверяется не форматирование, а полнота картины. Пропущенный в сводке
компонент — это отказ, о котором никто не узнает: панель горит зелёным,
пока хранилище или второй узел лежат.
"""

import pytest

from app.core.config import settings
from app.services import cluster, system_health


@pytest.mark.asyncio
async def test_s3_mode_shows_both_buckets_separately(monkeypatch):
    """Два независимых бакета — две карточки.

    Одна общая строка «файловое хранилище» скрыла бы отказ зеркала, а оно
    существует ровно для того, чтобы пережить отказ основного.
    """
    monkeypatch.setattr(settings, "storage_backend", "s3")

    async def fake(name, config):
        return {"name": name, "label": config.label, "status": "ok"}

    monkeypatch.setattr(system_health, "_check_bucket", fake)
    checks = await system_health._check_storage()

    assert [c["name"] for c in checks] == ["s3_primary", "s3_mirror"]


@pytest.mark.asyncio
async def test_local_mode_keeps_single_card(monkeypatch):
    monkeypatch.setattr(settings, "storage_backend", "local")
    checks = await system_health._check_storage()

    assert len(checks) == 1
    assert checks[0]["name"] == "storage"


@pytest.mark.asyncio
async def test_unconfigured_mirror_is_a_warning_not_a_failure(monkeypatch):
    """Зеркала нет — это предупреждение: система работает, но без страховки.
    Отсутствие ОСНОВНОГО бакета — уже отказ, вложения складывать некуда."""
    monkeypatch.setattr(settings, "storage_backend", "s3")
    monkeypatch.setattr(settings, "s3_primary_endpoint", "")
    monkeypatch.setattr(settings, "s3_mirror_endpoint", "")

    checks = await system_health._check_storage()
    by_name = {c["name"]: c for c in checks}

    assert by_name["s3_primary"]["status"] == "down"
    assert by_name["s3_mirror"]["status"] == "warn"


@pytest.mark.asyncio
async def test_cluster_shows_both_nodes_with_role(monkeypatch):
    monkeypatch.setattr(settings, "peer_url", "http://10.8.0.2/api/cluster/ping")
    monkeypatch.setattr(settings, "node_name", "A")

    async def snapshot():
        return {
            "node": "A", "role": cluster.PRIMARY, "read_only": False,
            "sync_configured": False, "replicas": [{"sync_state": "async", "lag_seconds": 0.2}],
            "lag_seconds": None, "peer": {"alive": True, "latency_ms": 27},
        }

    monkeypatch.setattr(cluster, "snapshot", snapshot)
    checks = await system_health._check_cluster()

    assert [c["name"] for c in checks] == ["node_self", "node_peer"]
    assert "главный" in checks[0]["label"]
    assert checks[1]["status"] == "ok"
    assert checks[1]["latency_ms"] == 27


@pytest.mark.asyncio
async def test_dead_peer_is_visible(monkeypatch):
    """Молчащий сосед должен быть красным, а не отсутствовать в сводке."""
    monkeypatch.setattr(settings, "peer_url", "http://10.8.0.2/api/cluster/ping")

    async def snapshot():
        return {
            "node": "A", "role": cluster.STANDBY, "read_only": False,
            "sync_configured": False, "replicas": [], "lag_seconds": 0.0,
            "peer": {"alive": False, "detail": "соединение отклонено"},
        }

    monkeypatch.setattr(cluster, "snapshot", snapshot)
    checks = await system_health._check_cluster()

    assert checks[1]["status"] == "down"
    assert "резерв" in checks[0]["label"]


@pytest.mark.asyncio
async def test_no_cluster_configured_adds_nothing(monkeypatch):
    monkeypatch.setattr(settings, "peer_url", "")
    assert await system_health._check_cluster() == []
