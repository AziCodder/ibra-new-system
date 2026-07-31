"""add_user_session_version

Revision ID: e1b2c3d4f5a6
Revises: d7a1f9c3b5e2
Create Date: 2026-07-21

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'e1b2c3d4f5a6'
down_revision: str | Sequence[str] | None = 'd7a1f9c3b5e2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "session_version")
