"""CLI script to create the first admin user.

Usage:
    python -m app.scripts.create_admin <login> <password> [full_name]
"""

import asyncio
import sys

from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.user import User, UserRole


async def create_admin(login: str, password: str, full_name: str = "") -> None:
    async with async_session_factory() as session:
        existing = await session.execute(select(User).where(User.login == login))
        if existing.scalar_one_or_none():
            print(f"User '{login}' already exists.")
            sys.exit(1)

        user = User(
            login=login,
            password_hash=hash_password(password),
            role=UserRole.admin,
            full_name=full_name,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        print(f"Admin '{login}' created successfully.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m app.scripts.create_admin <login> <password> [full_name]")
        sys.exit(1)

    login_arg = sys.argv[1]
    password_arg = sys.argv[2]
    name_arg = sys.argv[3] if len(sys.argv) > 3 else ""

    asyncio.run(create_admin(login_arg, password_arg, name_arg))
