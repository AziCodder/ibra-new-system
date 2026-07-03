"""Create a PostgreSQL logical backup (pg_dump) from DATABASE_URL.

Usage:
    python -m app.scripts.backup_db [output_dir]

Requires `pg_dump` on PATH (PostgreSQL client tools).
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings


def _parse_database_url(url: str) -> dict[str, str]:
    # postgresql+asyncpg://user:pass@host:port/dbname
    normalized = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    parsed = urlparse(normalized)
    if parsed.scheme not in {"postgresql", "postgres"} or not parsed.hostname or not parsed.path:
        raise ValueError(f"Unsupported DATABASE_URL: {url}")
    return {
        "host": parsed.hostname,
        "port": str(parsed.port or 5432),
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
        "dbname": parsed.path.lstrip("/"),
    }


def backup_database(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    target = output_dir / f"ibra_orders_{stamp}.sql"

    conn = _parse_database_url(settings.database_url)
    env = os.environ.copy()
    if conn["password"]:
        env["PGPASSWORD"] = conn["password"]

    cmd = [
        "pg_dump",
        "-h",
        conn["host"],
        "-p",
        conn["port"],
        "-U",
        conn["user"],
        "-d",
        conn["dbname"],
        "--no-owner",
        "--no-privileges",
        "-f",
        str(target),
    ]
    subprocess.run(cmd, check=True, env=env)
    return target


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("backups")
    path = backup_database(out)
    print(f"Backup written to {path}")
