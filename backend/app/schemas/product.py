from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    supplier_id: int
    name: str = Field(min_length=1, max_length=255)
    details: str = ""
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(ge=0)
    currency: str = "USD"
    photo_key: str | None = None


class ProductUpdate(BaseModel):
    supplier_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    details: str | None = None
    quantity: Decimal | None = Field(default=None, gt=0)
    price: Decimal | None = Field(default=None, ge=0)
    currency: str | None = None
    photo_key: str | None = None


class ProductOut(BaseModel):
    id: int
    order_id: int
    supplier_id: int
    supplier_name: str
    name: str
    details: str
    quantity: Decimal
    price: Decimal
    currency: str
    photo_key: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
