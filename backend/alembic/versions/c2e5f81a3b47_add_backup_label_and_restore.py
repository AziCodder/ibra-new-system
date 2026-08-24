"""add backup label and restore fields

Имя ручной копии и результат отката на неё.

Revision ID: c2e5f81a3b47
Revises: b7d4e9a2c518
Create Date: 2026-08-24 12:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c2e5f81a3b47'
down_revision: str | Sequence[str] | None = 'b7d4e9a2c518'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BACKUP_STATUSES = ('running', 'ok', 'failed')


def upgrade() -> None:
    """Upgrade schema."""
    status = postgresql.ENUM(*BACKUP_STATUSES, name='backup_status', create_type=False)
    op.add_column('backup_runs', sa.Column('label', sa.String(length=200), nullable=False, server_default=''))
    op.add_column('backup_runs', sa.Column('restored_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('backup_runs', sa.Column('restore_status', status, nullable=True))
    op.add_column('backup_runs', sa.Column('restore_detail', sa.Text(), nullable=False, server_default=''))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('backup_runs', 'restore_detail')
    op.drop_column('backup_runs', 'restore_status')
    op.drop_column('backup_runs', 'restored_at')
    op.drop_column('backup_runs', 'label')
