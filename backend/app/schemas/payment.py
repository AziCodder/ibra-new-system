from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.core.currency import Currency


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: Currency
    exchange_rate: Decimal = Field(gt=0, max_digits=14, decimal_places=6)
    file_key: str | None = None
    note: str = ""
    paid_at: datetime | None = None


class PaymentUpdate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: Currency
    exchange_rate: Decimal = Field(gt=0, max_digits=14, decimal_places=6)
    file_key: str | None = None
    note: str = ""
    paid_at: datetime


class PaymentOut(BaseModel):
    id: int
    payment_request_id: int
    author_id: int
    author_name: str
    amount: Decimal
    currency: Currency
    exchange_rate: Decimal
    file_key: str | None
    note: str
    paid_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
