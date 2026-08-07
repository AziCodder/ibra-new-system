from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.core.currency import Currency
from app.models.logistics import LogisticsStatus


def _strip_tracking(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class LogisticsItemIn(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class LogisticsItemOut(BaseModel):
    product_id: int
    product_name: str
    quantity: Decimal


class LogisticsCreate(BaseModel):
    items: list[LogisticsItemIn] = Field(min_length=1)
    tracking: str | None = None
    ship_date: datetime
    invoice_file_key: str | None = None
    details: str = ""
    status: LogisticsStatus = LogisticsStatus.in_transit
    received_date: datetime | None = None
    expense_amount: Decimal | None = Field(default=None, max_digits=14, decimal_places=2)
    currency: Currency | None = None
    exchange_rate: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=6)
    acceptance_note: str | None = None

    @field_validator("tracking")
    @classmethod
    def _validate_tracking(cls, value: str | None) -> str | None:
        return _strip_tracking(value)


class LogisticsUpdate(BaseModel):
    """Excludes receipt fields — those only change via accept/unaccept, atomically."""

    # Replaces the shipment's lines wholesale when present, like payment request items.
    items: list[LogisticsItemIn] | None = Field(default=None, min_length=1)
    tracking: str | None = None
    ship_date: datetime | None = None
    invoice_file_key: str | None = None
    details: str | None = None
    status: LogisticsStatus | None = None

    @field_validator("tracking")
    @classmethod
    def _validate_tracking(cls, value: str | None) -> str | None:
        return _strip_tracking(value)


class LogisticsAccept(BaseModel):
    received_date: datetime
    expense_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: Currency
    exchange_rate: Decimal = Field(gt=0, max_digits=14, decimal_places=6)
    note: str = ""


class LogisticsOut(BaseModel):
    id: int
    order_id: int
    items: list[LogisticsItemOut]
    created_by_id: int
    created_by_name: str
    # Sum of the lines' quantities — only meaningful as a rough size indicator
    # when a shipment mixes products measured in different units.
    total_quantity: Decimal
    tracking: str | None
    ship_date: datetime
    invoice_file_key: str | None
    details: str
    status: LogisticsStatus
    received_date: datetime | None
    expense_amount: Decimal | None
    currency: Currency | None
    exchange_rate: Decimal | None
    acceptance_note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LogisticsSummaryOut(LogisticsOut):
    order_number: str
    order_currency: Currency
    client_name: str
    manager_name: str
    manager_id: int


class NotifyLogisticsReceivedIn(BaseModel):
    group_ids: list[int] | None = None
