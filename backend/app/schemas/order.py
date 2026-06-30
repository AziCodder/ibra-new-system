from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.order import OrderStatus


class OrderCreate(BaseModel):
    client_id: int
    currency: str = "USD"
    details: str = ""


class OrderUpdate(BaseModel):
    details: str


class OrderOut(BaseModel):
    id: int
    number: str
    client_id: int
    client_name: str
    manager_id: int
    manager_name: str
    status: OrderStatus
    currency: str
    details: str
    created_at: datetime
    profit_pct: Decimal | None = None
    processing_days: int | None = None

    model_config = {"from_attributes": True}


class OrderListOut(BaseModel):
    items: list[OrderOut]
    total: int
    page: int
    page_size: int
