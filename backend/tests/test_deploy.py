"""Smoke checks for production deploy artifacts (Phase 15.3)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


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
