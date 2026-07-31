from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.requests import Request
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.cookies import session_cookie_params
from app.core.database import get_session
from app.core.security import verify_password
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, UserResponse
from app.services.rate_limit import is_blocked, record_failure

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_COOKIE = "session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days

serializer = URLSafeTimedSerializer(settings.session_secret)


def _make_session_token(user_id: int, session_version: int) -> str:
    return serializer.dumps({"uid": user_id, "v": session_version})


def _read_session_token(token: str) -> dict | None:
    try:
        return serializer.loads(token, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return None


async def get_current_user(request: Request, session: AsyncSession = Depends(get_session)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    data = _read_session_token(token)
    if data is None or "uid" not in data:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    result = await session.execute(select(User).where(User.id == data["uid"]))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or deactivated")

    if data.get("v") != user.session_version:
        raise HTTPException(status_code=401, detail="Session has been revoked, please log in again")

    return user


def require_role(*roles: UserRole) -> Callable:
    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return Depends(dependency)


@router.post("/login", response_model=UserResponse)
async def login(body: LoginRequest, request: Request, response: Response, session: AsyncSession = Depends(get_session)):
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{body.login}:{client_ip}"
    if await is_blocked(rate_key):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")

    result = await session.execute(select(User).where(User.login == body.login))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        await record_failure(rate_key)
        raise HTTPException(status_code=401, detail="Invalid login or password")

    if not user.is_active:
        # Same response as a wrong password — don't let this distinguish
        # "exists but disabled" from "wrong credentials" for an attacker.
        raise HTTPException(status_code=401, detail="Invalid login or password")

    token = _make_session_token(user.id, user.session_version)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_MAX_AGE,
        **session_cookie_params(),
    )
    return user


@router.post("/logout")
async def logout(
    response: Response,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user.session_version += 1
    await session.commit()
    response.delete_cookie(key=SESSION_COOKIE, **session_cookie_params())
    return {"ok": True}


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user
