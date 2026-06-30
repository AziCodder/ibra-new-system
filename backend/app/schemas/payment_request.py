from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.payment_request import PaymentRequestPriority

MAX_FILES = 3


class PaymentRequestItemIn(BaseModel):
    product_id: int
    amount: Decimal = Field(gt=0)


class PaymentRequestCreate(BaseModel):
    requisites: str = ""
    details: str = ""
    priority: PaymentRequestPriority = PaymentRequestPriority.normal
    file_keys: list[str] = Field(default_factory=list, max_length=MAX_FILES)
    items: list[PaymentRequestItemIn] = Field(min_length=1)


class PaymentRequestUpdate(BaseModel):
    requisites: str | None = None
    details: str | None = None
    priority: PaymentRequestPriority | None = None
    file_keys: list[str] | None = Field(default=None, max_length=MAX_FILES)
    items: list[PaymentRequestItemIn] | None = Field(default=None, min_length=1)


class PaymentRequestItemOut(BaseModel):
    id: int
    product_id: int
    product_name: str
    amount: Decimal

    model_config = {"from_attributes": True}


class PaymentRequestOut(BaseModel):
    id: int
    order_id: int
    created_by_id: int
    created_by_name: str
    requisites: str
    details: str
    priority: PaymentRequestPriority
    file_keys: list[str]
    currency: str
    total_amount: Decimal
    paid_amount: Decimal
    remaining_amount: Decimal
    items: list[PaymentRequestItemOut]
    created_at: datetime

    model_config = {"from_attributes": True}


class PaymentRequestSummaryOut(PaymentRequestOut):
    order_number: str
    client_name: str
    manager_name: str
    manager_id: int
    order_currency: str
