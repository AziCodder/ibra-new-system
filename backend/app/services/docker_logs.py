"""Чтение РЕАЛЬНЫХ логов контейнеров для админки («Логи процессов»).

Источник — те же логи, что отдаёт ``docker logs``: бэкенд ходит в Docker Engine
API не напрямую, а через read-only ``docker-socket-proxy`` (см. docker-compose),
которому разрешены только GET ``/containers/json`` и ``/containers/{id}/logs``.
Сам ``/var/run/docker.sock`` в контейнер бэкенда не монтируется — компрометация
API не даёт доступа к хосту.

Модуль разбит на «чистую» часть (парсинг строк, определение уровня, фильтрация —
без Docker, легко тестируется) и тонкие обёртки над Docker SDK. ``docker``
импортируется лениво внутри ``_client()``, поэтому модуль грузится даже там, где
пакета нет (тесты подменяют клиент фейком).
"""

from __future__ import annotations

import re
import socket
from datetime import datetime, timezone
from typing import Iterable, Optional

from app.core.config import settings


class LogsUnavailable(Exception):
    """Docker-прокси недоступен / функция выключена — отдаётся как 503, а не 500."""


class UnknownSource(Exception):
    """Запрошен сервис, которого нет среди контейнеров проекта."""


# ─────────────────────────────────────────────────────── чистая часть (логика)

# Канонические уровни и синонимы из вывода uvicorn / postgres / прочих процессов.
_LEVEL_ALIASES = {
    "CRITICAL": "CRITICAL", "FATAL": "CRITICAL", "PANIC": "CRITICAL",
    "ERROR": "ERROR", "ERR": "ERROR",
    "WARNING": "WARNING", "WARN": "WARNING",
    "NOTICE": "INFO", "INFO": "INFO", "LOG": "INFO",
    "DEBUG": "DEBUG", "TRACE": "DEBUG",
}
LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

_LEVEL_RE = re.compile(
    r"\b(" + "|".join(sorted(_LEVEL_ALIASES, key=len, reverse=True)) + r")\b"
)
# Docker --timestamps: RFC3339(Nano), напр. 2026-06-26T10:00:00.123456789Z
_TS_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$"
)


def _parse_ts(token: str) -> Optional[datetime]:
    """Разобрать префикс-метку времени Docker. None — если это не метка."""
    m = _TS_RE.match(token)
    if not m:
        return None
    base, frac, tz = m.groups()
    frac = (frac or "")[:7]  # datetime принимает максимум 6 знаков дробной части
    if tz in (None, "Z"):
        tz = "+00:00"
    elif ":" not in tz:  # +0300 → +03:00
        tz = tz[:3] + ":" + tz[3:]
    try:
        return datetime.fromisoformat(base + frac + tz)
    except ValueError:
        return None


def _detect_level(message: str) -> str:
    """Уровень строки лога (для фильтра «по типу»). '' — если не распознан."""
    m = _LEVEL_RE.search(message)
    return _LEVEL_ALIASES[m.group(1)] if m else ""


def parse_log_lines(raw: bytes | str) -> list[dict]:
    """Сырой вывод ``docker logs -t`` → список {ts, level, text}.

    ``text`` — строка ровно как её вывел процесс (без добавленной Docker метки
    времени), ``ts`` — ISO-метка из префикса (или None), ``level`` — распознанный
    уровень. Так лог совпадает «точь в точь» с ``docker logs``.
    """
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    out: list[dict] = []
    for line in raw.splitlines():
        if not line:
            continue
        token, _, rest = line.partition(" ")
        ts = _parse_ts(token)
        text = rest if ts is not None else line
        out.append({
            "ts": ts.astimezone(timezone.utc).isoformat() if ts else None,
            "level": _detect_level(text),
            "text": text,
        })
    return out


def filter_lines(
    lines: Iterable[dict],
    *,
    search: Optional[str] = None,
    levels: Optional[Iterable[str]] = None,
) -> list[dict]:
    """Отфильтровать строки по подстроке (без регистра) и набору уровней."""
    lvset = {lvl.upper() for lvl in levels} if levels else None
    needle = search.strip().lower() if search else None
    out = []
    for ln in lines:
        if lvset is not None and ln["level"] not in lvset:
            continue
        if needle and needle not in ln["text"].lower():
            continue
        out.append(ln)
    return out


# ────────────────────────────────────────────────────── Docker-обёртки (тонкие)


def _client():  # pragma: no cover - требует реального docker/прокси, в тестах подменяется
    """Docker-клиент, нацеленный на read-only прокси. Лениво импортирует docker."""
    try:
        import docker  # noqa: PLC0415 — ленивый импорт: модуль грузится без пакета
    except ImportError as e:  # pragma: no cover - в проде пакет всегда установлен
        raise LogsUnavailable("Пакет docker не установлен на бэкенде") from e
    try:
        return docker.DockerClient(base_url=settings.docker_proxy_url, timeout=8)
    except Exception as e:  # pragma: no cover - сетевые ошибки конструктора редки
        raise LogsUnavailable(f"Не удалось подключиться к docker-proxy: {e}") from e


def _project(client) -> Optional[str]:
    """Имя compose-проекта для отсечения чужих контейнеров на том же хосте."""
    if settings.compose_project:
        return settings.compose_project
    try:
        me = client.containers.get(socket.gethostname())
        return (me.labels or {}).get("com.docker.compose.project")
    except Exception:  # pragma: no cover - best-effort: при сбое показываем все контейнеры
        return None


def _summaries(client) -> list:
    """Контейнеры проекта (docker SDK отдаёт по ним полный inspect)."""
    proj = _project(client)
    filters = {"label": f"com.docker.compose.project={proj}"} if proj else {}
    try:
        return client.containers.list(all=True, filters=filters)
    except Exception as e:
        raise LogsUnavailable(f"docker-proxy недоступен: {e}") from e


# Поля контейнера достаём устойчиво к структуре: docker SDK ``list()`` отдаёт
# inspect (labels под Config.Labels, State — словарь), но на всякий случай
# поддерживаем и плоскую списочную сводку (Labels/State на верхнем уровне).
def _labels(c) -> dict:
    a = getattr(c, "attrs", {}) or {}
    return (a.get("Config") or {}).get("Labels") or a.get("Labels") or {}


def _state(c) -> str:
    a = getattr(c, "attrs", {}) or {}
    st = a.get("State")
    if isinstance(st, dict):
        s = st.get("Status") or ""
        code = st.get("ExitCode")
        return f"{s} ({code})" if s == "exited" and code else s
    return st or ""


def _image(c) -> str:
    a = getattr(c, "attrs", {}) or {}
    return (a.get("Config") or {}).get("Image") or a.get("Image") or ""


def _service(c) -> str:
    return _labels(c).get("com.docker.compose.service") or c.name


def list_sources(client=None) -> list[dict]:
    """Список процессов (сервисов) проекта — для выпадашки «чьи логи»."""
    if not settings.logs_viewer_enabled:
        raise LogsUnavailable("Просмотр логов отключён (LOGS_VIEWER_ENABLED=false)")
    client = client or _client()
    out: list[dict] = []
    for c in _summaries(client):
        out.append({
            "name": _service(c),
            "container": c.name,
            "state": _state(c),
            "image": _image(c),
        })
    out.sort(key=lambda s: s["name"])
    return out


def read_logs(
    source: str,
    *,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    tail: int = 500,
    search: Optional[str] = None,
    levels: Optional[Iterable[str]] = None,
    client=None,
) -> list[dict]:
    """Прочитать и отфильтровать логи одного сервиса проекта.

    ``source`` валидируется по списку контейнеров проекта (нельзя прочитать
    произвольный чужой контейнер). ``since``/``until`` — окно по времени.
    """
    if not settings.logs_viewer_enabled:
        raise LogsUnavailable("Просмотр логов отключён (LOGS_VIEWER_ENABLED=false)")
    client = client or _client()
    container = next(
        (c for c in _summaries(client) if _service(c) == source or c.name == source),
        None,
    )
    if container is None:
        raise UnknownSource(source)
    try:
        raw = container.logs(
            stdout=True, stderr=True, timestamps=True, tail=tail,
            since=int(since.timestamp()) if since else None,
            until=int(until.timestamp()) if until else None,
        )
    except Exception as e:  # pragma: no cover - защита от особенностей docker SDK
        raise LogsUnavailable(f"Не удалось получить логи {source}: {e}") from e
    lines = parse_log_lines(raw)
    return filter_lines(lines, search=search, levels=levels)
