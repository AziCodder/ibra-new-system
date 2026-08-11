"""invert the direction every exchange rate is stored in

Rates used to be stored as "target-currency units per 1 operation-currency unit",
so converting multiplied: a RUB product on a CNY order carried 0.086957 and the
form asked "1 RUB = ? CNY". Every form now asks the other way round — "1 CNY =
? RUB" -> 11.5 — which reads naturally (the order's currency first) and matches
how rates are quoted in practice. Converting therefore divides, and every stored
rate has to be inverted so existing orders keep their current totals.

Rows already at 1 are left alone (inverting them is a no-op) and so are the
non-positive rates that the API cannot produce but a hand-written row could —
inverting those would divide by zero.

The column is Numeric(14, 6), so a plain 1/rate often lands on a value like
11.500057 where the user originally typed 11.5. To avoid filling the UI with that
noise, the shortest rounding (2, then 4, then 6 decimals) that still inverts back
to the exact stored rate wins.

Revision ID: d4c8b2a71f60
Revises: c7e3b1d84f92
Create Date: 2026-08-08

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4c8b2a71f60'
down_revision: str | Sequence[str] | None = 'c7e3b1d84f92'
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
