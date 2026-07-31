"""add_payment_paid_at

Revision ID: 22c86ac7e1bc
Revises: e1b2c3d4f5a6
Create Date: 2026-07-29 21:44:14.312007

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '22c86ac7e1bc'
down_revision: Union[str, Sequence[str], None] = 'e1b2c3d4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('payments', sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE payments SET paid_at = created_at WHERE paid_at IS NULL")
    op.alter_column('payments', 'paid_at', nullable=False, server_default=sa.func.now())


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('payments', 'paid_at')
