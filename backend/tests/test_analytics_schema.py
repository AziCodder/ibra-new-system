"""Tests for analytics schema fields and indexes (task 14.1)."""

import pytest
from sqlalchemy import inspect, text

from app.core.database import engine
from app.models.order import Order


@pytest.mark.asyncio
async def test_orders_table_has_analytics_indexes():
    """Composite indexes for future client/manager/period reports exist on orders."""
    async with engine.connect() as conn:
        def _collect(sync_conn):
            return {idx["name"] for idx in inspect(sync_conn).get_indexes("orders")}

        names = await conn.run_sync(_collect)

    expected = {
        "ix_orders_client_created",
        "ix_orders_client_status",
        "ix_orders_manager_created",
        "ix_orders_status",
        "ix_orders_completed_at",
        "ix_orders_number",
    }
    assert expected.issubset(names)


@pytest.mark.asyncio
async def test_orders_table_has_analytics_columns():
    """Closing date and volume/profit snapshot columns are present."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'orders'
                  AND column_name IN ('completed_at', 'total_income', 'profit_amount')
                """
            )
        )
        cols = {row[0] for row in result}

    assert cols == {"completed_at", "total_income", "profit_amount"}


def test_order_model_exposes_analytics_fields():
    """ORM model includes analytics snapshot + closing date fields."""
    assert "completed_at" in Order.__table__.columns
    assert "total_income" in Order.__table__.columns
    assert "profit_amount" in Order.__table__.columns
