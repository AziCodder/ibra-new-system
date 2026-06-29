from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.routers.auth import require_role
from app.schemas.user import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/", response_model=list[UserOut])
async def list_users(
    _admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).order_by(User.id))
    return result.scalars().all()


@router.post("/", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate,
    _admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
):
    existing = await session.execute(select(User).where(User.login == body.login))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Login already exists")

    user = User(
        login=body.login,
        password_hash=hash_password(body.password),
        role=body.role,
        full_name=body.full_name,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    body: UserUpdate,
    _admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.full_name is not None:
        user.full_name = body.full_name
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password is not None:
        user.password_hash = hash_password(body.password)

    await session.commit()
    await session.refresh(user)
    return user
