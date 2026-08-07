"""HARDEN — edge-case validation."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.client import ClientCreate
from app.schemas.ledger_entry import LedgerEntryCreate, LedgerEntryType
from app.schemas.logistics import LogisticsAccept, LogisticsCreate, LogisticsItemIn
from app.schemas.payment import PaymentCreate
from app.schemas.product import ProductCreate
from app.schemas.supplier import SupplierCreate


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


def test_ledger_rejects_zero_amount():
    with pytest.raises(ValidationError):
        LedgerEntryCreate(
            type=LedgerEntryType.income,
            amount=Decimal("0"),
            currency="USD",
            exchange_rate=Decimal("1"),
        )


def test_ledger_rejects_negative_amount():
    with pytest.raises(ValidationError):
        LedgerEntryCreate(
            type=LedgerEntryType.income,
            amount=Decimal("-10"),
            currency="USD",
            exchange_rate=Decimal("1"),
        )


def test_payment_rejects_negative_exchange_rate():
    with pytest.raises(ValidationError):
        PaymentCreate(amount=Decimal("10"), currency="USD", exchange_rate=Decimal("-0.5"))


def test_payment_rejects_zero_amount():
    with pytest.raises(ValidationError):
        PaymentCreate(amount=Decimal("0"), currency="USD", exchange_rate=Decimal("1"))


def test_logistics_accept_rejects_negative_exchange_rate():
    from datetime import datetime, timezone

    with pytest.raises(ValidationError):
        LogisticsAccept(
            received_date=datetime.now(timezone.utc),
            expense_amount=Decimal("100"),
            currency="USD",
            exchange_rate=Decimal("-1"),
        )


def test_logistics_accept_rejects_zero_expense_amount():
    from datetime import datetime, timezone

    with pytest.raises(ValidationError):
        LogisticsAccept(
            received_date=datetime.now(timezone.utc),
            expense_amount=Decimal("0"),
            currency="USD",
            exchange_rate=Decimal("1"),
        )


def test_logistics_create_rejects_negative_exchange_rate():
    from datetime import datetime, timezone

    with pytest.raises(ValidationError):
        LogisticsCreate(
                    items=[LogisticsItemIn(product_id=1, quantity=Decimal("1"))],
                    ship_date=datetime.now(timezone.utc),
            exchange_rate=Decimal("-2"),
        )


def test_logistics_create_allows_null_exchange_rate():
    from datetime import datetime, timezone

    row = LogisticsCreate(
                    items=[LogisticsItemIn(product_id=1, quantity=Decimal("1"))],
                    ship_date=datetime.now(timezone.utc),
        exchange_rate=None,
    )
    assert row.exchange_rate is None


def test_client_rejects_full_name_over_db_limit():
    with pytest.raises(ValidationError):
        ClientCreate(full_name="x" * 256)


def test_supplier_rejects_name_over_db_limit():
    with pytest.raises(ValidationError):
        SupplierCreate(name="x" * 256)


def test_product_rejects_name_over_db_limit():
    with pytest.raises(ValidationError):
        ProductCreate(supplier_id=1, name="x" * 256, quantity=Decimal("1"), price=Decimal("1"))


def test_product_rejects_zero_quantity():
    with pytest.raises(ValidationError):
        ProductCreate(supplier_id=1, name="Item", quantity=Decimal("0"), price=Decimal("1"))
