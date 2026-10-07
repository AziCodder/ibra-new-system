"""product exchange rate optional

Курс товара к валюте заказа больше не обязателен: в прибыли он не участвует
(закупки считаются по курсу каждой оплаты), только в строке «итого в валюте
заказа». NULL = курс не указан.

Revision ID: a7c3e9f1d2b6
Revises: c2e5f81a3b47
Create Date: 2026-10-05 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7c3e9f1d2b6'
down_revision: str | Sequence[str] | None = 'c2e5f81a3b47'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # The server default goes too: the API always writes the rate explicitly, and a
    # default would make SQLAlchemy store 1 where the API meant NULL.
    op.alter_column(
        'products', 'exchange_rate', existing_type=sa.Numeric(14, 6), nullable=True, server_default=None
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute('UPDATE products SET exchange_rate = 1 WHERE exchange_rate IS NULL')
    op.alter_column(
        'products', 'exchange_rate', existing_type=sa.Numeric(14, 6), nullable=False, server_default='1'
    )
