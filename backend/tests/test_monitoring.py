"""Logging and health monitoring (Phase 15.4)."""

import json
import logging
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.logging_config import JsonFormatter, setup_logging
from app.main import app
from app.middleware.request_logging import unhandled_exception_handler


def test_json_formatter_outputs_structured_line():
    setup_logging(production=True)
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.method = "GET"
    record.path = "/api/orders"
    record.status_code = 200
    line = JsonFormatter().format(record)
    data = json.loads(line)
    assert data["level"] == "INFO"
    assert data["message"] == "hello"
    assert data["method"] == "GET"
    assert data["path"] == "/api/orders"
    assert data["status_code"] == 200


@pytest.mark.asyncio
async def test_health_live():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_ready_checks_database():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["db"] == "ok"
    assert body["status"] == "ok"


@pytest.mark.asyncio
async def test_unhandled_exception_handler_returns_500():
    request = MagicMock()
    request.method = "GET"
    request.url.path = "/broken"
    resp = await unhandled_exception_handler(request, RuntimeError("probe failure"))
    assert resp.status_code == 500
    assert resp.body == b'{"detail":"Internal server error"}'
