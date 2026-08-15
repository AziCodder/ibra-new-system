"""mark telegram groups the bot has been removed from

Chats are linked to clients by hand now, so the links have to outlive the bot
being kicked from a chat and re-added: previously that event deleted them.
Instead the chat is flagged inactive and stops being a delivery target.

Revision ID: c58a1e7b3d94
Revises: f6b2d90a4c17
Create Date: 2026-08-15

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c58a1e7b3d94'
down_revision: str | Sequence[str] | None = 'f6b2d90a4c17'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'telegram_groups',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('telegram_groups', 'is_active')
