"""add stored_files registry

Реестр файлов во внешнем хранилище: что где лежит и совпадает ли.

Revision ID: a3f7c1d05e42
Revises: c58a1e7b3d94
Create Date: 2026-08-24 01:10:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a3f7c1d05e42'
down_revision: str | Sequence[str] | None = 'c58a1e7b3d94'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REPLICA_STATES = ('ok', 'pending', 'error', 'missing', 'disabled')


def upgrade() -> None:
    """Upgrade schema."""
    # Тип создаём отдельно и один раз; в create_table он идёт уже с
    # create_type=False, иначе SQLAlchemy попытается создать его повторно.
    replica_state = postgresql.ENUM(*REPLICA_STATES, name='replica_state', create_type=False)
    postgresql.ENUM(*REPLICA_STATES, name='replica_state').create(op.get_bind(), checkfirst=True)

    op.create_table(
        'stored_files',
        sa.Column('key', sa.String(length=255), primary_key=True),
        sa.Column('filename', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('size', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('sha256', sa.String(length=64), nullable=False, server_default=''),
        sa.Column('primary_state', replica_state, nullable=False, server_default='pending'),
        sa.Column('mirror_state', replica_state, nullable=False, server_default='pending'),
        sa.Column('last_error', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('replicated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )
    # Фоновая дозаливка ищет именно отставшие копии — без индекса это
    # полный проход по всему реестру каждые несколько минут.
    op.create_index(
        'ix_stored_files_primary_state', 'stored_files', ['primary_state']
    )
    op.create_index(
        'ix_stored_files_mirror_state', 'stored_files', ['mirror_state']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_stored_files_mirror_state', table_name='stored_files')
    op.drop_index('ix_stored_files_primary_state', table_name='stored_files')
    op.drop_table('stored_files')
    sa.Enum(name='replica_state').drop(op.get_bind(), checkfirst=True)
