import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import delete

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.main import app
from app.models.user import User, UserRole
from app.schemas.user import UserCreate
from app.services import rate_limit as rl


async def _create_user(login: str, password: str, is_active: bool = True) -> User:
    async with async_session_factory() as session:
        user = User(
            login=login,
            password_hash=hash_password(password),
            role=UserRole.manager,
            full_name="Auth Test",
            is_active=is_active,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _cleanup(user_id: int) -> None:
    async with async_session_factory() as session:
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_logout_invalidates_previously_issued_token(client):
    user = await _create_user("auth_logout_test", "correcthorse123")
    try:
        login_res = await client.post(
            "/api/auth/login", json={"login": "auth_logout_test", "password": "correcthorse123"}
        )
        assert login_res.status_code == 200
        old_cookie = client.cookies.get("session")
        assert old_cookie

        me_res = await client.get("/api/auth/me")
        assert me_res.status_code == 200

        logout_res = await client.post("/api/auth/logout")
        assert logout_res.status_code == 200

        # Replay the pre-logout cookie (simulates a stolen/copied token) — must be rejected now.
        client.cookies.set("session", old_cookie)
        replay_res = await client.get("/api/auth/me")
        assert replay_res.status_code == 401
    finally:
        await _cleanup(user.id)


@pytest.mark.asyncio
async def test_deactivated_account_gets_same_error_as_wrong_password(client):
    user = await _create_user("auth_deactivated_test", "correcthorse123", is_active=False)
    try:
        res = await client.post(
            "/api/auth/login", json={"login": "auth_deactivated_test", "password": "correcthorse123"}
        )
        assert res.status_code == 401
        assert res.json()["detail"] == "Invalid login or password"
    finally:
        await _cleanup(user.id)


@pytest.mark.asyncio
async def test_rate_limit_blocks_after_five_failures_and_self_clears(client, monkeypatch):
    fake_now = [0.0]
    monkeypatch.setattr(rl.time, "monotonic", lambda: fake_now[0])
    rl._attempts.clear()

    user = await _create_user("auth_ratelimit_test", "correcthorse123")
    try:
        for _ in range(5):
            res = await client.post(
                "/api/auth/login", json={"login": "auth_ratelimit_test", "password": "wrong"}
            )
            assert res.status_code == 401

        blocked = await client.post(
            "/api/auth/login", json={"login": "auth_ratelimit_test", "password": "wrong"}
        )
        assert blocked.status_code == 429

        # Even the correct password is blocked while the window is still active.
        still_blocked = await client.post(
            "/api/auth/login", json={"login": "auth_ratelimit_test", "password": "correcthorse123"}
        )
        assert still_blocked.status_code == 429

        fake_now[0] += rl.WINDOW_SECONDS + 1
        recovered = await client.post(
            "/api/auth/login", json={"login": "auth_ratelimit_test", "password": "correcthorse123"}
        )
        assert recovered.status_code == 200
    finally:
        rl._attempts.clear()
        await _cleanup(user.id)


def test_user_create_rejects_short_password():
    with pytest.raises(ValidationError):
        UserCreate(login="short_pw_test", password="short")


def test_user_create_accepts_eight_char_password():
    created = UserCreate(login="ok_pw_test", password="12345678")
    assert created.password == "12345678"
