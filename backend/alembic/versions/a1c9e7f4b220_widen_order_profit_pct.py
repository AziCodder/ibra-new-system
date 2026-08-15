"""widen_order_profit_pct

Revision ID: a1c9e7f4b220
Revises: e4f8a2b1c903
Create Date: 2026-07-13

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1c9e7f4b220"
down_revision: str | Sequence[str] | None = "e4f8a2b1c903"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "orders",
        "profit_pct",
        existing_type=sa.Numeric(precision=8, scale=4),
        type_=sa.Numeric(precision=12, scale=4),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "orders",
        "profit_pct",
        existing_type=sa.Numeric(precision=12, scale=4),
        type_=sa.Numeric(precision=8, scale=4),
        existing_nullable=True,
    )
