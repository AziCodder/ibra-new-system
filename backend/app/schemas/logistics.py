from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.logistics import LogisticsStatus


class LogisticsCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0)
    tracking: str = ""
    ship_date: datetime
    invoice_file_key: str | None = None
    details: str = ""
    status: LogisticsStatus = LogisticsStatus.in_transit
    received_date: datetime | None = None
    expense_amount: Decimal | None = None
    currency: str | None = None
    exchange_rate: Decimal | None = Field(default=None, gt=0)
    acceptance_note: str | None = None


class LogisticsUpdate(BaseModel):
    """Excludes receipt fields — those only change via accept/unaccept, atomically."""

    quantity: Decimal | None = Field(default=None, gt=0)
    tracking: str | None = None
    ship_date: datetime | None = None
    invoice_file_key: str | None = None
    details: str | None = None
    status: LogisticsStatus | None = None


class LogisticsAccept(BaseModel):
    received_date: datetime
    expense_amount: Decimal = Field(gt=0)
    currency: str
    exchange_rate: Decimal = Field(gt=0)
    note: str = ""


class LogisticsOut(BaseModel):
    id: int
    order_id: int
    product_id: int
    product_name: str
    created_by_id: int
    created_by_name: str
    quantity: Decimal
    tracking: str
    ship_date: datetime
    invoice_file_key: str | None
    details: str
    status: LogisticsStatus
    received_date: datetime | None
    expense_amount: Decimal | None
    currency: str | None
    exchange_rate: Decimal | None
    acceptance_note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LogisticsSummaryOut(LogisticsOut):
    order_number: str
    client_name: str
    manager_name: str
    manager_id: int
