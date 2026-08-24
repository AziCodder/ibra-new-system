"""Smoke checks for production deploy artifacts (Phase 15.3)."""

from pathlib import Path


def _find_project_root() -> Path:
    # Walk up from this file until we find a dir with both backend/ and frontend/.
    # Works locally (parents[2]) and inside Docker when /workspace is mounted.
    for p in Path(__file__).resolve().parents:
        if (p / "backend").is_dir() and (p / "frontend").is_dir():
            return p
    # Fallback: /workspace mount added to docker-compose.yml
    ws = Path("/workspace")
    if ws.is_dir():
        return ws
    return Path(__file__).resolve().parents[2]


ROOT = _find_project_root()


def test_prod_dockerfiles_exist():
    assert (ROOT / "backend" / "Dockerfile.prod").is_file()
    assert (ROOT / "frontend" / "Dockerfile.prod").is_file()


def test_backend_entrypoint_runs_migrations():
    entry = (ROOT / "backend" / "docker-entrypoint.sh").read_text(encoding="utf-8")
    assert "alembic upgrade head" in entry
    assert "uvicorn" in entry


def test_frontend_nginx_proxies_api():
    nginx = (ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    assert "location /api/" in nginx
    assert "proxy_pass http://backend:8000" in nginx
    assert "try_files" in nginx


def test_compose_prod_is_standalone():
    compose = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    assert "docker-compose.yml" not in compose
    assert "Dockerfile.prod" in compose
    assert "profiles: [\"backup\"]" in compose or 'profiles: ["backup"]' in compose


def test_deploy_script_exists():
    assert (ROOT / "scripts" / "deploy.sh").is_file()


def _compose_files():
    return [
        (ROOT / "docker-compose.yml").read_text(encoding="utf-8"),
        (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"),
    ]


def test_worker_service_runs_the_scheduler():
    for compose in _compose_files():
        assert "python -m app.workers.scheduler" in compose


def test_backend_and_worker_share_the_backup_directory():
    """Ручной бэкап снимает backend, а по расписанию — worker.

    Разъедься у них каталоги — откат искал бы файл не там, где он лежит,
    и «копия есть, а восстановить нечем».
    """
    for compose in _compose_files():
        assert compose.count("BACKUP_DIR: /var/lib/ibra/backups") == 2
        assert compose.count("backups:/var/lib/ibra/backups") == 2


def test_postgres_client_is_installed_for_backups():
    """pg_dump/pg_restore нужны и API (ручной бэкап, откат), и воркеру."""
    for name in ("Dockerfile", "Dockerfile.prod"):
        text = (ROOT / "backend" / name).read_text(encoding="utf-8")
        assert "postgresql-client-16" in text
