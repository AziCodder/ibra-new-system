"""add_order_profit_metrics

Revision ID: c3a7f91e2d05
Revises: 489cc621f268
Create Date: 2026-07-01

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'c3a7f91e2d05'
down_revision: str | Sequence[str] | None = '489cc621f268'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('profit_pct', sa.Numeric(precision=8, scale=4), nullable=True))
    op.add_column('orders', sa.Column('processing_days', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('orders', 'processing_days')
    op.drop_column('orders', 'profit_pct')
