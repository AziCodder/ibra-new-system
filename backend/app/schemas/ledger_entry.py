from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.ledger_entry import LedgerEntryType


class LedgerEntryCreate(BaseModel):
    type: LedgerEntryType
    amount: Decimal = Field(gt=0)
    currency: str
    exchange_rate: Decimal = Field(gt=0)
    details: str = ""


class LedgerEntryOut(BaseModel):
    id: int
    order_id: int
    author_id: int
    author_name: str
    type: LedgerEntryType
    amount: Decimal
    currency: str
    exchange_rate: Decimal
    details: str
    created_at: datetime

    model_config = {"from_attributes": True}
