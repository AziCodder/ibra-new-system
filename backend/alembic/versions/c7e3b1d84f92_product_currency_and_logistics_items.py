"""product exchange rate + multi-product logistics

Two related schema changes:

1. `products.exchange_rate` — a product may now be priced in a currency other
   than its order's. The rate ("order-currency units per 1 product-currency
   unit") lets profit.py value those purchases in the order's currency. Existing
   rows all match their order's currency, so they backfill to 1.

2. `logistics_items` — a shipment used to carry exactly one product
   (`logistics.product_id` + `logistics.quantity`); it now carries a list of
   lines. Every existing shipment migrates to a single line, then the two
   columns are dropped.

Revision ID: c7e3b1d84f92
Revises: 39d99fd35f53
Create Date: 2026-08-07

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c7e3b1d84f92'
down_revision: str | Sequence[str] | None = '39d99fd35f53'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'products',
        sa.Column('exchange_rate', sa.Numeric(14, 6), nullable=False, server_default='1'),
    )

    op.create_table(
        'logistics_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('logistics_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Numeric(14, 3), nullable=False),
        sa.ForeignKeyConstraint(['logistics_id'], ['logistics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('logistics_id', 'product_id', name='uq_logistics_items_logistics_product'),
    )
    op.create_index('ix_logistics_items_product', 'logistics_items', ['product_id'])

    # Each existing shipment becomes a one-line shipment — no data is lost.
    op.execute(
        """
        INSERT INTO logistics_items (logistics_id, product_id, quantity)
        SELECT id, product_id, quantity FROM logistics
        """
    )

    op.drop_column('logistics', 'product_id')
    op.drop_column('logistics', 'quantity')


def downgrade() -> None:
    """Downgrade schema.

    Lossy by nature: a shipment with several lines cannot be represented by the
    old single-product columns, so only its first line survives. Shipments with
    no lines at all (impossible via the API, but possible by hand) are dropped,
    since the restored columns are NOT NULL.
    """
    op.add_column('logistics', sa.Column('product_id', sa.Integer(), nullable=True))
    op.add_column('logistics', sa.Column('quantity', sa.Numeric(14, 3), nullable=True))

    op.execute(
        """
        UPDATE logistics l
        SET product_id = first_line.product_id, quantity = first_line.quantity
        FROM (
            SELECT DISTINCT ON (logistics_id) logistics_id, product_id, quantity
            FROM logistics_items
            ORDER BY logistics_id, id
        ) AS first_line
        WHERE first_line.logistics_id = l.id
        """
    )
    op.execute("DELETE FROM logistics WHERE product_id IS NULL")

    op.alter_column('logistics', 'product_id', nullable=False)
    op.alter_column('logistics', 'quantity', nullable=False)
    op.create_foreign_key('logistics_product_id_fkey', 'logistics', 'products', ['product_id'], ['id'])

    op.drop_index('ix_logistics_items_product', table_name='logistics_items')
    op.drop_table('logistics_items')

    op.drop_column('products', 'exchange_rate')
