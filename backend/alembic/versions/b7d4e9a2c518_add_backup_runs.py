"""add backup_runs journal

Журнал резервных копий: что сделано, куда залито, разворачивается ли.

Revision ID: b7d4e9a2c518
Revises: a3f7c1d05e42
Create Date: 2026-08-24 02:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b7d4e9a2c518'
down_revision: str | Sequence[str] | None = 'a3f7c1d05e42'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BACKUP_KINDS = ('hourly', 'daily', 'manual')
BACKUP_STATUSES = ('running', 'ok', 'failed')
REPLICA_STATES = ('ok', 'pending', 'error', 'missing', 'disabled')


def upgrade() -> None:
    """Upgrade schema."""
    postgresql.ENUM(*BACKUP_KINDS, name='backup_kind').create(op.get_bind(), checkfirst=True)
    postgresql.ENUM(*BACKUP_STATUSES, name='backup_status').create(op.get_bind(), checkfirst=True)

    kind = postgresql.ENUM(*BACKUP_KINDS, name='backup_kind', create_type=False)
    status = postgresql.ENUM(*BACKUP_STATUSES, name='backup_status', create_type=False)
    # Тип уже создан миграцией реестра файлов — переиспользуем его.
    replica_state = postgresql.ENUM(*REPLICA_STATES, name='replica_state', create_type=False)

    op.create_table(
        'backup_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('kind', kind, nullable=False),
        sa.Column('status', status, nullable=False, server_default='running'),
        sa.Column('object_key', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('local_path', sa.String(length=500), nullable=False, server_default=''),
        sa.Column('size', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('sha256', sa.String(length=64), nullable=False, server_default=''),
        sa.Column('primary_state', replica_state, nullable=False, server_default='pending'),
        sa.Column('mirror_state', replica_state, nullable=False, server_default='pending'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error', sa.Text(), nullable=False, server_default=''),
        sa.Column('node', sa.String(length=100), nullable=False, server_default=''),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verify_status', status, nullable=True),
        sa.Column('verify_detail', sa.Text(), nullable=False, server_default=''),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )
    # Чистка по сроку хранения и вкладка «Бэкапы» ходят именно так:
    # «часовые старше даты» и «последние по времени».
    op.create_index('ix_backup_runs_kind_started', 'backup_runs', ['kind', 'started_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_backup_runs_kind_started', table_name='backup_runs')
    op.drop_table('backup_runs')
    sa.Enum(name='backup_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='backup_kind').drop(op.get_bind(), checkfirst=True)
