from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.core.currency import Currency

# A payment is always made in the currency its request is denominated in — the
# operator pays off part of that request, so there is nothing to choose. The
# currency is therefore not accepted from the client; it is read off the request.
#
# `exchange_rate` is the rate the payer bought that currency at, quoted towards
# the order's currency: "1 CNY = 11.5 RUB" -> 11.5. Multiplying gives what the
# payment costs in the order's totals, which is the only thing the rate feeds.
# It is 1 when the request is already denominated in the order's currency.


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    exchange_rate: Decimal = Field(gt=0, max_digits=14, decimal_places=6)
    file_key: str | None = None
    note: str = ""
    paid_at: datetime | None = None


class PaymentUpdate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
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
