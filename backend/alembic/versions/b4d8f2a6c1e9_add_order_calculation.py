"""add order calculation

Расчёт заказа: прибыль делится между участниками по процентам, после чего
заказ замораживается до отмены расчёта.

Revision ID: b4d8f2a6c1e9
Revises: a7c3e9f1d2b6
Create Date: 2026-10-05 12:10:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b4d8f2a6c1e9'
down_revision: str | Sequence[str] | None = 'a7c3e9f1d2b6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('orders', sa.Column('calculated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('orders', sa.Column('calculated_profit', sa.Numeric(14, 2), nullable=True))
    op.create_table(
        'order_calculation_participants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('percent', sa.Numeric(5, 2), nullable=False),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.UniqueConstraint('order_id', 'user_id', name='uq_order_calculation_participant'),
    )
    op.create_index(
        'ix_order_calculation_participants_order_id', 'order_calculation_participants', ['order_id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_order_calculation_participants_order_id', table_name='order_calculation_participants')
    op.drop_table('order_calculation_participants')
    op.drop_column('orders', 'calculated_profit')
    op.drop_column('orders', 'calculated_at')
