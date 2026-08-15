from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.core.currency import Currency, CurrencyIn


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: CurrencyIn
    # Units of the payment request's currency per 1 unit of `currency` — a CNY
    # payment on a RUB request reads "1 CNY = 11.5 RUB" -> 11.5, so converting
    # multiplies. 1 when they match.
    exchange_rate: Decimal = Field(gt=0, max_digits=14, decimal_places=6)
    file_key: str | None = None
    note: str = ""
    paid_at: datetime | None = None


class PaymentUpdate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    # A legacy EUR payment therefore has to be re-saved in a current currency.
    currency: CurrencyIn
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
