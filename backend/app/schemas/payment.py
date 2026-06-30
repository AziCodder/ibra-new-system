from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: str
    exchange_rate: Decimal = Field(gt=0)
    file_key: str | None = None
    note: str = ""


class PaymentOut(BaseModel):
    id: int
    payment_request_id: int
    author_id: int
    author_name: str
    amount: Decimal
    currency: str
    exchange_rate: Decimal
    file_key: str | None
    note: str
    created_at: datetime

    model_config = {"from_attributes": True}
