import pytest

from app.core.config import settings
from app.core.database import async_session_factory
from app.routers.system_health import get_system_health
from app.services import system_health


@pytest.fixture(autouse=True)
def _unreachable_probe_targets(monkeypatch):
    """Point probes at a closed local port so unit tests fail fast (connection
    refused) instead of waiting out DNS/timeout for the docker-network hosts."""
    monkeypatch.setattr(settings, "health_frontend_base", "http://127.0.0.1:1")
    monkeypatch.setattr(settings, "health_self_base", "http://127.0.0.1:1")


@pytest.mark.asyncio
async def test_collect_reports_all_sections_and_marks_unreachable_probes_down():
    async with async_session_factory() as session:
        report = await system_health.collect(session)

    assert report["enabled"] is True
    assert report["checked_at"] is not None

    service_names = {s["name"] for s in report["services"]}
    assert service_names == {"backend", "database", "storage", "frontend"}

    backend = next(s for s in report["services"] if s["name"] == "backend")
    assert backend["status"] == "ok"

    database = next(s for s in report["services"] if s["name"] == "database")
    assert database["status"] == "ok"  # runs against the real test DB

    frontend = next(s for s in report["services"] if s["name"] == "frontend")
    assert frontend["status"] == "down"  # unreachable target from fixture

    page_names = {p["name"] for p in report["pages"] if p["kind"] == "page"}
    assert page_names == set(system_health.FRONTEND_PAGES)
    api_names = {p["name"] for p in report["pages"] if p["kind"] == "api"}
    assert api_names == set(system_health.API_ENDPOINTS)
    assert all(p["status"] == "down" and p["status_code"] is None for p in report["pages"])

    # Backend/DB/storage all healthy but frontend+probes down → overall degraded, not worst-case.
    assert report["overall"] == "down"


@pytest.mark.asyncio
async def test_collect_disabled_returns_empty_report(monkeypatch):
    monkeypatch.setattr(settings, "health_check_enabled", False)
    async with async_session_factory() as session:
        report = await system_health.collect(session)

    assert report == {
        "enabled": False,
        "overall": "ok",
        "services": [],
        "pages": [],
        "checked_at": report["checked_at"],
    }


@pytest.mark.asyncio
async def test_status_for_code_thresholds():
    assert system_health.status_for_code(200) == "ok"
    assert system_health.status_for_code(404) == "warn"
    assert system_health.status_for_code(500) == "down"


@pytest.mark.asyncio
async def test_collect_uses_ok_probes_when_targets_reachable(monkeypatch):
    """A reachable target with 200s should flip frontend/pages/apis back to ok."""

    class _FakeResponse:
        status_code = 200

    class _FakeClient:
        async def get(self, url, follow_redirects=True):
            return _FakeResponse()

        async def aclose(self):
            pass

    async with async_session_factory() as session:
        report = await system_health.collect(session, client=_FakeClient())  # type: ignore[arg-type]

    assert report["overall"] == "ok"
    frontend = next(s for s in report["services"] if s["name"] == "frontend")
    assert frontend["status"] == "ok"
    assert all(p["status"] == "ok" and p["status_code"] == 200 for p in report["pages"])


@pytest.mark.asyncio
async def test_get_system_health_endpoint_returns_report_for_admin(monkeypatch):
    monkeypatch.setattr(settings, "health_check_enabled", False)
    async with async_session_factory() as session:
        result = await get_system_health(_admin=None, session=session)  # type: ignore[arg-type]

    assert result["enabled"] is False
    assert result["overall"] == "ok"
