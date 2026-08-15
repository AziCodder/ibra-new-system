"""quote every exchange rate from the record's currency to the target one

d4c8b2a71f60 stored rates as "operation-currency units per 1 target-currency
unit", so a CNY expense on a RUB order carried 0.086957 and the form asked
"1 RUB = ? CNY". Every form now asks the other way round — "1 CNY = ? RUB" ->
11.5 — because the number people actually quote is the one that starts with the
currency they paid in. Converting therefore multiplies, and every stored rate has
to be inverted so existing orders keep their current totals.

The inversion, its guards (rates at 1 and non-positive rates are left alone) and
the shortest-rounding trick that keeps 11.5 from becoming 11.500057 are the same
as in d4c8b2a71f60 — this revision simply flips the direction back.

Revision ID: f6b2d90a4c17
Revises: d4c8b2a71f60
Create Date: 2026-08-15

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f6b2d90a4c17'
down_revision: str | Sequence[str] | None = 'd4c8b2a71f60'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every table holding a rate. The inversion is its own inverse, so upgrade and
# downgrade run exactly the same statement.
RATE_TABLES = ('products', 'payments', 'ledger_entries', 'logistics')


def _invert(table: str) -> None:
    op.execute(
        f"""
        UPDATE {table}
        SET exchange_rate = CASE
            -- NULLIF keeps a rate that rounds away to zero (1/2000 at 2 decimals)
            -- from raising a division-by-zero here; NULL simply fails the match.
            WHEN ROUND(1 / NULLIF(ROUND(1 / exchange_rate, 2), 0), 6) = exchange_rate
                THEN ROUND(1 / exchange_rate, 2)
            WHEN ROUND(1 / NULLIF(ROUND(1 / exchange_rate, 4), 0), 6) = exchange_rate
                THEN ROUND(1 / exchange_rate, 4)
            ELSE ROUND(1 / exchange_rate, 6)
        END
        WHERE exchange_rate > 0 AND exchange_rate <> 1
        """
    )


def upgrade() -> None:
    """Upgrade schema."""
    for table in RATE_TABLES:
        _invert(table)


def downgrade() -> None:
    """Downgrade schema."""
    for table in RATE_TABLES:
        _invert(table)
