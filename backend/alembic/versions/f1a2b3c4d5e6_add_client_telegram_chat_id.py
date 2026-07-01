"""add_client_telegram_chat_id

Revision ID: f1a2b3c4d5e6
Revises: c3a7f91e2d05
Create Date: 2026-07-02

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'f1a2b3c4d5e6'
down_revision: str | Sequence[str] | None = 'c3a7f91e2d05'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column("telegram_chat_id", sa.String(length=64), server_default="", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("clients", "telegram_chat_id")
