"""add_order_file_keys

Revision ID: fe73288e3791
Revises: b1f4a7c2e9d3
Create Date: 2026-07-30 20:40:08.843357

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'fe73288e3791'
down_revision: str | Sequence[str] | None = 'b1f4a7c2e9d3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'orders',
        sa.Column('file_keys', postgresql.ARRAY(sa.String(length=255)), nullable=False, server_default='{}'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('orders', 'file_keys')
