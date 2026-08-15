from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.core.currency import Currency, CurrencyIn
from app.models.order import OrderStatus

MAX_ORDER_FILES = 5


class OrderCreate(BaseModel):
    client_id: int
    currency: CurrencyIn = CurrencyIn.RUB
    details: str = ""
    manager_id: int | None = None
    file_keys: list[str] = Field(default_factory=list, max_length=MAX_ORDER_FILES)


class OrderUpdate(BaseModel):
    details: str
    manager_id: int | None = None


class OrderFileAdd(BaseModel):
    file_key: str


class OrderReorderIn(BaseModel):
    """id заказов видимой страницы в новом (перетащенном) порядке."""

    order_ids: list[int]


class OrderOut(BaseModel):
    id: int
    number: str
    client_id: int
    client_name: str
    manager_id: int
    manager_name: str
    status: OrderStatus
    currency: Currency
    details: str
    file_keys: list[str] = []
    created_at: datetime
    completed_at: datetime | None = None
    profit_pct: Decimal | None = None
    processing_days: int | None = None
    total_income: Decimal | None = None
    profit_amount: Decimal | None = None
    # None = no payment request created yet for this order ("ждёт счёт")
    requested_amount: Decimal | None = None
    paid_amount: Decimal | None = None

    model_config = {"from_attributes": True}


class OrderListOut(BaseModel):
    items: list[OrderOut]
    total: int
    page: int
    page_size: int


class OrderStatsOut(BaseModel):
    total_count: int
    total_count_delta_month: int
    in_progress_count: int
    waiting_payment_count: int
    completed_count: int
    completed_pct_month: float | None
    profit_month: dict[str, Decimal]
    profit_month_delta_pct: float | None
