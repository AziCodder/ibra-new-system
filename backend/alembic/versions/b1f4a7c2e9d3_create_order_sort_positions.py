"""create_order_sort_positions

Revision ID: b1f4a7c2e9d3
Revises: 22c86ac7e1bc
Create Date: 2026-07-30

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'b1f4a7c2e9d3'
down_revision: str | Sequence[str] | None = '22c86ac7e1bc'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'order_sort_positions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'order_id', name='uq_order_sort_position_user_order'),
    )
    op.create_index('ix_order_sort_positions_user', 'order_sort_positions', ['user_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_order_sort_positions_user', table_name='order_sort_positions')
    op.drop_table('order_sort_positions')
