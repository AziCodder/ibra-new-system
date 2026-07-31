from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.ledger_entry import LedgerEntryCreate
from app.schemas.logistics import LogisticsCreate
from app.schemas.order import OrderCreate
from app.schemas.payment import PaymentCreate
from app.schemas.product import ProductCreate


def test_order_rejects_unknown_currency():
    with pytest.raises(ValidationError):
        OrderCreate(client_id=1, currency="ZZZ")


def test_product_rejects_unknown_currency():
    with pytest.raises(ValidationError):
        ProductCreate(supplier_id=1, name="Widget", quantity=Decimal("1"), price=Decimal("1"), currency="ZZZ")


def test_payment_rejects_unknown_currency():
    with pytest.raises(ValidationError):
        PaymentCreate(amount=Decimal("1"), currency="ZZZ", exchange_rate=Decimal("1"))


def test_ledger_entry_rejects_unknown_currency():
    with pytest.raises(ValidationError):
        LedgerEntryCreate(type="income", amount=Decimal("1"), currency="ZZZ", exchange_rate=Decimal("1"))


def test_order_accepts_known_currency():
    created = OrderCreate(client_id=1, currency="RUB")
    assert created.currency == "RUB"


def test_tracking_is_trimmed():
    created = LogisticsCreate(product_id=1, quantity=Decimal("1"), ship_date=datetime.now(UTC), tracking="  M77-1  ")
    assert created.tracking == "M77-1"


def test_whitespace_only_tracking_becomes_none():
    created = LogisticsCreate(product_id=1, quantity=Decimal("1"), ship_date=datetime.now(UTC), tracking="   ")
    assert created.tracking is None


def test_product_name_rejects_whitespace_only():
    with pytest.raises(ValidationError):
        ProductCreate(supplier_id=1, name="   ", quantity=Decimal("1"), price=Decimal("1"))


def test_product_name_accepts_normal_value():
    created = ProductCreate(supplier_id=1, name="Widget", quantity=Decimal("1"), price=Decimal("1"))
    assert created.name == "Widget"
