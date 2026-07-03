"""Shared session cookie parameters (dev vs production)."""

from app.core.config import settings


def session_cookie_params() -> dict[str, object]:
    params: dict[str, object] = {
        "httponly": True,
        "samesite": settings.cookie_samesite,
        "path": "/",
    }
    if settings.cookie_secure:
        params["secure"] = True
    return params
