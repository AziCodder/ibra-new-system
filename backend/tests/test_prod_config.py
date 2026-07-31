"""Production security settings (Phase 15.2)."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.cookies import session_cookie_params


def test_development_allows_default_secret():
    s = Settings(app_env="development", session_secret="change-me-to-random-string")
    assert not s.is_production
    assert not s.cookie_secure


def test_production_rejects_default_secret():
    with pytest.raises(ValidationError, match="SESSION_SECRET"):
        Settings(
            app_env="production",
            session_secret="change-me-to-random-string",
            cors_origins=["https://app.example.com"],
            trusted_hosts=["app.example.com"],
        )


def test_production_rejects_cors_wildcard():
    with pytest.raises(ValidationError, match="wildcard"):
        Settings(
            app_env="production",
            session_secret="x" * 32,
            cors_origins=["*"],
            trusted_hosts=["app.example.com"],
        )


def test_production_requires_trusted_hosts():
    with pytest.raises(ValidationError, match="TRUSTED_HOSTS"):
        Settings(
            app_env="production",
            session_secret="x" * 32,
            cors_origins=["https://app.example.com"],
            trusted_hosts=[],
        )


def test_session_cookie_params_secure_in_production():
    from unittest.mock import patch

    prod = Settings(
        app_env="production",
        session_secret="x" * 32,
        cors_origins=["https://app.example.com"],
        trusted_hosts=["app.example.com"],
    )
    assert prod.cookie_secure is True
    with patch("app.core.cookies.settings", prod):
        params = session_cookie_params()
    assert params["secure"] is True
    assert params["httponly"] is True


def test_parse_cors_origins_from_comma_string():
    s = Settings(cors_origins="https://a.com, https://b.com")
    assert s.cors_origins == ["https://a.com", "https://b.com"]


def test_parse_cors_origins_from_env_var(monkeypatch):
    # Env vars go through pydantic-settings' EnvSettingsSource, a different code
    # path from init kwargs: complex-typed fields get JSON-decoded *before* our
    # mode="before" validator runs, unless annotated with NoDecode. Regression
    # test for a real prod outage — this failed with a bare SettingsError even
    # though test_parse_cors_origins_from_comma_string above passed.
    monkeypatch.setenv("CORS_ORIGINS", "https://a.com,https://b.com")
    monkeypatch.setenv("TRUSTED_HOSTS", "a.com,b.com")
    s = Settings()
    assert s.cors_origins == ["https://a.com", "https://b.com"]
    assert s.trusted_hosts == ["a.com", "b.com"]
