"""create_telegram_groups_tables

Revision ID: d7a1f9c3b5e2
Revises: c9d1e2f3a4b5
Create Date: 2026-07-15

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'd7a1f9c3b5e2'
down_revision: str | Sequence[str] | None = 'c9d1e2f3a4b5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_telegram_groups_chat_id"), "telegram_groups", ["chat_id"], unique=True)

    op.create_table(
        "client_telegram_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["telegram_groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", "group_id", name="uix_client_telegram_groups_client_group"),
    )


def downgrade() -> None:
    op.drop_table("client_telegram_groups")
    op.drop_index(op.f("ix_telegram_groups_chat_id"), table_name="telegram_groups")
    op.drop_table("telegram_groups")
