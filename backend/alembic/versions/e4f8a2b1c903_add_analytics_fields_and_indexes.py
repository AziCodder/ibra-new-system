"""add_analytics_fields_and_indexes

Revision ID: e4f8a2b1c903
Revises: b8d42f0a1c37
Create Date: 2026-07-03

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e4f8a2b1c903"
down_revision: str | Sequence[str] | None = "b8d42f0a1c37"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("total_income", sa.Numeric(precision=14, scale=2), nullable=True))
    op.add_column("orders", sa.Column("profit_amount", sa.Numeric(precision=14, scale=2), nullable=True))

    op.create_index("ix_orders_client_created", "orders", ["client_id", "created_at"])
    op.create_index("ix_orders_client_status", "orders", ["client_id", "status"])
    op.create_index("ix_orders_manager_created", "orders", ["manager_id", "created_at"])
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_completed_at", "orders", ["completed_at"])


def downgrade() -> None:
    op.drop_index("ix_orders_completed_at", table_name="orders")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_orders_manager_created", table_name="orders")
    op.drop_index("ix_orders_client_status", table_name="orders")
    op.drop_index("ix_orders_client_created", table_name="orders")

    op.drop_column("orders", "profit_amount")
    op.drop_column("orders", "total_income")
    op.drop_column("orders", "completed_at")
