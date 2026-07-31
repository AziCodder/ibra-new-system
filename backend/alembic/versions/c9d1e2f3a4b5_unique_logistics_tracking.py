"""unique_logistics_tracking

Revision ID: c9d1e2f3a4b5
Revises: a1c9e7f4b220
Create Date: 2026-07-15

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'c9d1e2f3a4b5'
down_revision: str | Sequence[str] | None = 'a1c9e7f4b220'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Convert empty-string tracking values to NULL so they don't conflict
    # with the unique constraint (PostgreSQL treats NULL != NULL in unique indexes)
    op.execute("UPDATE logistics SET tracking = NULL WHERE tracking = ''")

    # Make column nullable
    op.alter_column(
        'logistics', 'tracking',
        existing_type=sa.String(length=255),
        nullable=True,
    )

    # Add unique index; NULLs are excluded from uniqueness checks in PostgreSQL
    op.create_index(
        'uix_logistics_tracking',
        'logistics',
        ['tracking'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('uix_logistics_tracking', table_name='logistics')

    op.execute("UPDATE logistics SET tracking = '' WHERE tracking IS NULL")

    op.alter_column(
        'logistics', 'tracking',
        existing_type=sa.String(length=255),
        nullable=False,
    )
