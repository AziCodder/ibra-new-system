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
    exchange_rate: Decimal | None = None


class LogisticsUpdate(BaseModel):
    quantity: Decimal | None = Field(default=None, gt=0)
    tracking: str | None = None
    ship_date: datetime | None = None
    invoice_file_key: str | None = None
    details: str | None = None
    status: LogisticsStatus | None = None
    received_date: datetime | None = None
    expense_amount: Decimal | None = None
    currency: str | None = None
    exchange_rate: Decimal | None = None


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
    created_at: datetime

    model_config = {"from_attributes": True}
