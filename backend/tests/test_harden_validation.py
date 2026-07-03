"""HARDEN — edge-case validation (negative/zero exchange rates)."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.ledger_entry import LedgerEntryCreate, LedgerEntryType
from app.schemas.logistics import LogisticsAccept, LogisticsCreate
from app.schemas.payment import PaymentCreate


def test_ledger_rejects_negative_exchange_rate():
    with pytest.raises(ValidationError):
        LedgerEntryCreate(
            type=LedgerEntryType.income,
            amount=Decimal("100"),
            currency="USD",
            exchange_rate=Decimal("-1"),
        )


def test_ledger_rejects_zero_exchange_rate():
    with pytest.raises(ValidationError):
        LedgerEntryCreate(
            type=LedgerEntryType.income,
            amount=Decimal("100"),
            currency="USD",
            exchange_rate=Decimal("0"),
        )


def test_payment_rejects_negative_exchange_rate():
    with pytest.raises(ValidationError):
        PaymentCreate(amount=Decimal("10"), currency="USD", exchange_rate=Decimal("-0.5"))


def test_logistics_accept_rejects_negative_exchange_rate():
    from datetime import datetime, timezone

    with pytest.raises(ValidationError):
        LogisticsAccept(
            received_date=datetime.now(timezone.utc),
            expense_amount=Decimal("100"),
            currency="USD",
            exchange_rate=Decimal("-1"),
        )


def test_logistics_create_rejects_negative_exchange_rate():
    from datetime import datetime, timezone

    with pytest.raises(ValidationError):
        LogisticsCreate(
            product_id=1,
            quantity=Decimal("1"),
            ship_date=datetime.now(timezone.utc),
            exchange_rate=Decimal("-2"),
        )


def test_logistics_create_allows_null_exchange_rate():
    from datetime import datetime, timezone

    row = LogisticsCreate(
        product_id=1,
        quantity=Decimal("1"),
        ship_date=datetime.now(timezone.utc),
        exchange_rate=None,
    )
    assert row.exchange_rate is None
