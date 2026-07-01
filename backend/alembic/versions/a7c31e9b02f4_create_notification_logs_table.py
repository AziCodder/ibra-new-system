"""create_notification_logs_table

Revision ID: a7c31e9b02f4
Revises: f1a2b3c4d5e6
Create Date: 2026-07-02

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'a7c31e9b02f4'
down_revision: str | Sequence[str] | None = 'f1a2b3c4d5e6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # create_table emits CREATE TYPE for the named Enum column exactly once.
    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("target", sa.String(length=255), server_default="", nullable=False),
        sa.Column("message", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.Enum("sent", "failed", name="notification_status"), nullable=False),
        sa.Column("error", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("notification_logs")
    # drop_table does not remove the enum type; do it explicitly.
    sa.Enum(name="notification_status").drop(op.get_bind(), checkfirst=True)
