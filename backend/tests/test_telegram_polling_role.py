"""Опрос Telegram — только на главном узле.

Telegram отдаёт обновления одному подписчику. Если опрашивают оба узла
кластера, они перехватывают сообщения друг у друга и часть уведомлений
клиентам теряется — молча, без единой ошибки в интерфейсе.
"""

import pytest

from app.core.config import settings
from app.services import cluster, telegram_bot


@pytest.mark.asyncio
async def test_primary_polls(monkeypatch):
    monkeypatch.setattr(settings, "peer_url", "http://10.8.0.2/api/cluster/ping")

    async def role():
        return cluster.PRIMARY

    monkeypatch.setattr(cluster, "role", role)
    assert await telegram_bot.should_poll() is True


@pytest.mark.asyncio
async def test_standby_stays_silent(monkeypatch):
    monkeypatch.setattr(settings, "peer_url", "http://10.8.0.1/api/cluster/ping")

    async def role():
        return cluster.STANDBY

    monkeypatch.setattr(cluster, "role", role)
    assert await telegram_bot.should_poll() is False


@pytest.mark.asyncio
async def test_single_server_polls(monkeypatch):
    """Кластера нет — мешать некому, опрашиваем."""
    monkeypatch.setattr(settings, "peer_url", "")
    assert await telegram_bot.should_poll() is True


@pytest.mark.asyncio
async def test_unknown_role_stays_silent(monkeypatch):
    """База недоступна, роль неизвестна.

    Молчим: перехватить обновления у живого главного хуже, чем не отвечать.
    """
    monkeypatch.setattr(settings, "peer_url", "http://10.8.0.2/api/cluster/ping")

    async def role():
        raise RuntimeError("база недоступна")

    monkeypatch.setattr(cluster, "role", role)
    assert await telegram_bot.should_poll() is False
