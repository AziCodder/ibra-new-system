"""cascade_delete_order_products

Revision ID: 39d99fd35f53
Revises: fe73288e3791
Create Date: 2026-07-30 20:48:45.439783

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '39d99fd35f53'
down_revision: str | Sequence[str] | None = 'fe73288e3791'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint('products_order_id_fkey', 'products', type_='foreignkey')
    op.create_foreign_key(
        'products_order_id_fkey', 'products', 'orders', ['order_id'], ['id'], ondelete='CASCADE'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('products_order_id_fkey', 'products', type_='foreignkey')
    op.create_foreign_key('products_order_id_fkey', 'products', 'orders', ['order_id'], ['id'])
