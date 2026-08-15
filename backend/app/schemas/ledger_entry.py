from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.core.currency import Currency
from app.models.ledger_entry import LedgerEntryType


class LedgerEntryCreate(BaseModel):
    type: LedgerEntryType
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: Currency
    # Units of the order's currency per 1 unit of `currency` — a CNY entry in a
    # RUB order reads "1 CNY = 11.5 RUB" -> 11.5, so converting multiplies.
    # 1 when they match.
    exchange_rate: Decimal = Field(gt=0, max_digits=14, decimal_places=6)
    details: str = ""


class LedgerEntryOut(BaseModel):
    id: int
    order_id: int
    author_id: int
    author_name: str
    type: LedgerEntryType
    amount: Decimal
    currency: Currency
    exchange_rate: Decimal
    details: str
    created_at: datetime

    model_config = {"from_attributes": True}
