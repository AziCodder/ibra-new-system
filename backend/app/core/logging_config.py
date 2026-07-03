"""Application logging — structured JSON in production, plain text in dev.

All loggers write to stdout (single stream) for Docker/journald aggregation.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class JsonFormatter(logging.Formatter):
    """One JSON object per line — easy to grep and ship to log collectors."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("method", "path", "status_code", "duration_ms", "client"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(*, production: bool, level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    if production:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "app"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True

    # Uvicorn access logs are noisy duplicates when we log requests ourselves.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
