from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.ledger_entry import LedgerEntryCreate, LedgerEntryOut
from app.schemas.logistics import LogisticsCreate, LogisticsItemIn
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
    created = OrderCreate(client_id=1, currency="USD")
    assert created.currency == "USD"


def test_order_currency_defaults_to_rub():
    """Most orders are settled in roubles, so that is what the form opens on."""
    assert OrderCreate(client_id=1).currency == "RUB"


@pytest.mark.parametrize(
    "build",
    [
        lambda: OrderCreate(client_id=1, currency="EUR"),
        lambda: ProductCreate(supplier_id=1, name="Widget", quantity=Decimal("1"), price=Decimal("1"), currency="EUR"),
        lambda: PaymentCreate(amount=Decimal("1"), currency="EUR", exchange_rate=Decimal("1")),
        lambda: LedgerEntryCreate(type="income", amount=Decimal("1"), currency="EUR", exchange_rate=Decimal("1")),
    ],
)
def test_new_records_cannot_be_created_in_eur(build):
    """EUR was dropped from the pickers, so nothing new may be recorded in it."""
    with pytest.raises(ValidationError):
        build()


def test_records_already_stored_in_eur_still_load():
    """Output schemas keep EUR — rows written before it was dropped must stay readable."""
    out = LedgerEntryOut(
        id=1, order_id=1, author_id=1, author_name="Test", type="income",
        amount=Decimal("10"), currency="EUR", exchange_rate=Decimal("1"),
        details="", created_at=datetime.now(UTC),
    )
    assert out.currency == "EUR"


def test_tracking_is_trimmed():
    created = LogisticsCreate(
                    items=[LogisticsItemIn(product_id=1, quantity=Decimal("1"))],
                    ship_date=datetime.now(UTC), tracking="  M77-1  ")
    assert created.tracking == "M77-1"


def test_whitespace_only_tracking_becomes_none():
    created = LogisticsCreate(
                    items=[LogisticsItemIn(product_id=1, quantity=Decimal("1"))],
                    ship_date=datetime.now(UTC), tracking="   ")
    assert created.tracking is None


def test_product_name_rejects_whitespace_only():
    with pytest.raises(ValidationError):
        ProductCreate(supplier_id=1, name="   ", quantity=Decimal("1"), price=Decimal("1"))


def test_product_name_accepts_normal_value():
    created = ProductCreate(supplier_id=1, name="Widget", quantity=Decimal("1"), price=Decimal("1"))
    assert created.name == "Widget"
