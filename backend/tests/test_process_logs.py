from fastapi import HTTPException

from app.core.config import settings
from app.routers.process_logs import get_process_logs, list_process_log_sources
from app.services import docker_logs

# ───────────────────────────────────────────── чистая логика (без Docker)


def test_parse_log_lines_extracts_ts_level_text():
    raw = (
        b"2026-06-26T10:00:00.123456789Z INFO:     Application startup complete\n"
        b"\n"  # пустые строки пропускаются
        b"2026-06-26T10:00:01Z ERROR: boom\n"
        b"no-timestamp tail line\n"
    )
    lines = docker_logs.parse_log_lines(raw)
    assert len(lines) == 3
    assert lines[0]["level"] == "INFO"
    assert lines[0]["text"] == "INFO:     Application startup complete"
    assert lines[0]["ts"].startswith("2026-06-26T10:00:00")
    assert lines[1]["level"] == "ERROR"
    assert lines[2]["ts"] is None
    assert lines[2]["text"] == "no-timestamp tail line"


def test_detect_level_aliases():
    assert docker_logs._detect_level("FATAL: db down") == "CRITICAL"
    assert docker_logs._detect_level("[worker WARN] retry") == "WARNING"
    assert docker_logs._detect_level("LOG:  checkpoint complete") == "INFO"
    assert docker_logs._detect_level("plain line") == ""


def test_parse_ts_handles_offset_and_z():
    assert docker_logs._parse_ts("2026-06-26T10:00:00Z") is not None
    assert docker_logs._parse_ts("2026-06-26T10:00:00.5+0300") is not None
    assert docker_logs._parse_ts("not-a-timestamp") is None


def test_filter_lines_by_level_and_search():
    lines = [
        {"ts": None, "level": "INFO", "text": "user login ok"},
        {"ts": None, "level": "ERROR", "text": "payment failed for order 7"},
        {"ts": None, "level": "WARNING", "text": "slow query"},
    ]
    only_err = docker_logs.filter_lines(lines, levels=["ERROR"])
    assert [line["text"] for line in only_err] == ["payment failed for order 7"]

    found = docker_logs.filter_lines(lines, search="LOGIN")
    assert [line["text"] for line in found] == ["user login ok"]


# ─────────────────────────────────────── фейковый Docker-клиент для эндпоинтов


class _FakeContainer:
    """Повторяет структуру, которую отдаёт docker SDK ``containers.list()``:
    это ПОЛНЫЙ inspect — labels под Config.Labels, State — словарь (а не строка)."""

    def __init__(self, name, service, logbytes=b"", state="running", exit_code=0):
        self.name = name
        self.attrs = {
            "Config": {
                "Image": f"ibra/{service}:latest",
                "Labels": {
                    "com.docker.compose.service": service,
                    "com.docker.compose.project": "ibra-test",
                },
            },
            "State": {"Status": state, "ExitCode": exit_code},
        }
        self._logs = logbytes

    @property
    def labels(self):
        return self.attrs["Config"]["Labels"]

    def logs(self, **kwargs):
        return self._logs


class _FakeContainers:
    def __init__(self, items):
        self._items = items

    def list(self, all=False, filters=None):
        return self._items

    def get(self, name):
        return self._items[0]


class _FakeClient:
    def __init__(self, items):
        self.containers = _FakeContainers(items)


_SAMPLE = (
    b"2026-06-26T10:00:00Z INFO:     Application startup complete\n"
    b"2026-06-26T10:00:01Z ERROR: payment webhook signature mismatch\n"
    b"2026-06-26T10:00:02Z WARNING: slow query 1.2s\n"
)


def _fake_docker(monkeypatch):
    items = [
        _FakeContainer("ibra-backend-1", "backend", _SAMPLE),
        _FakeContainer("ibra-frontend-1", "frontend", b"", state="exited", exit_code=137),
    ]
    monkeypatch.setattr(docker_logs, "_client", lambda: _FakeClient(items))
    return items


# ───────────────────────────────────────────────────────────────── источники


async def test_sources_listed(monkeypatch):
    _fake_docker(monkeypatch)
    result = await list_process_log_sources(_admin=None)  # type: ignore[arg-type]
    assert result["available"] is True
    by_name = {s["name"]: s for s in result["items"]}
    assert {"backend", "frontend"} <= set(by_name)
    assert by_name["backend"]["state"] == "running"
    # State разбирается из словаря inspect'а: exited + код выхода.
    assert by_name["frontend"]["state"] == "exited (137)"
    assert by_name["backend"]["image"] == "ibra/backend:latest"
    assert "INFO" in result["levels"]


# ─────────────────────────────────────────────────────────── чтение и фильтры


async def test_logs_returns_parsed_lines(monkeypatch):
    _fake_docker(monkeypatch)
    result = await get_process_logs(  # type: ignore[arg-type]
        source="backend", since=None, until=None, level=None, q=None, tail=500, _admin=None,
    )
    assert result["source"] == "backend"
    assert result["count"] == 3
    assert result["lines"][0]["level"] == "INFO"
    assert result["lines"][1]["text"] == "ERROR: payment webhook signature mismatch"


async def test_logs_level_filter(monkeypatch):
    _fake_docker(monkeypatch)
    result = await get_process_logs(  # type: ignore[arg-type]
        source="backend", since=None, until=None, level=["ERROR"], q=None, tail=500, _admin=None,
    )
    assert result["count"] == 1
    assert result["lines"][0]["level"] == "ERROR"


async def test_logs_search_filter(monkeypatch):
    _fake_docker(monkeypatch)
    result = await get_process_logs(  # type: ignore[arg-type]
        source="backend", since=None, until=None, level=None, q="slow query", tail=500, _admin=None,
    )
    assert result["count"] == 1
    assert "slow query" in result["lines"][0]["text"]


async def test_logs_truncated_flag_set_when_tail_reached(monkeypatch):
    _fake_docker(monkeypatch)
    result = await get_process_logs(  # type: ignore[arg-type]
        source="backend", since=None, until=None, level=None, q=None, tail=3, _admin=None,
    )
    assert result["truncated"] is True


async def test_logs_unknown_source_404(monkeypatch):
    _fake_docker(monkeypatch)
    try:
        await get_process_logs(  # type: ignore[arg-type]
            source="ghost", since=None, until=None, level=None, q=None, tail=500, _admin=None,
        )
        assert False, "expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 404


# ──────────────────────────────────────────────────────────────── деградация


async def test_sources_graceful_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "logs_viewer_enabled", False)
    result = await list_process_log_sources(_admin=None)  # type: ignore[arg-type]
    assert result == {"items": [], "available": False, "detail": "Просмотр логов отключён (LOGS_VIEWER_ENABLED=false)"}


async def test_logs_503_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "logs_viewer_enabled", False)
    try:
        await get_process_logs(  # type: ignore[arg-type]
            source="backend", since=None, until=None, level=None, q=None, tail=500, _admin=None,
        )
        assert False, "expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 503


class _BrokenContainers:
    def list(self, all=False, filters=None):
        raise RuntimeError("connection refused")

    def get(self, name):
        raise RuntimeError("connection refused")


class _BrokenClient:
    containers = _BrokenContainers()


async def test_sources_graceful_when_proxy_down(monkeypatch):
    monkeypatch.setattr(docker_logs, "_client", lambda: _BrokenClient())
    result = await list_process_log_sources(_admin=None)  # type: ignore[arg-type]
    assert result["available"] is False
    assert result["detail"]


async def test_logs_503_when_proxy_down(monkeypatch):
    monkeypatch.setattr(docker_logs, "_client", lambda: _BrokenClient())
    try:
        await get_process_logs(  # type: ignore[arg-type]
            source="backend", since=None, until=None, level=None, q=None, tail=500, _admin=None,
        )
        assert False, "expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 503
