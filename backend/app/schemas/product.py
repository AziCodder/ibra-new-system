from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.core.currency import Currency
from app.models.logistics import LogisticsStatus


def _validate_name_not_blank(value: str | None) -> str | None:
    if value is None:
        return None
    if not value.strip():
        raise ValueError("name must not be blank")
    return value


class ProductCreate(BaseModel):
    supplier_id: int
    name: str = Field(min_length=1, max_length=255)
    details: str = ""
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    # Optional: the server always uses the order's currency (see create_product) —
    # if provided, it's only validated to match, never used to override it.
    currency: Currency | None = None
    photo_key: str | None = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        return _validate_name_not_blank(value)


class ProductUpdate(BaseModel):
    supplier_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    details: str | None = None
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=3)
    price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    currency: Currency | None = None
    photo_key: str | None = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str | None) -> str | None:
        return _validate_name_not_blank(value)


class ProductShipmentOut(BaseModel):
    """One logistics record of this product, for the product card's tracking list."""

    id: int
    tracking: str | None
    quantity: Decimal
    status: LogisticsStatus


class ProductOut(BaseModel):
    id: int
    order_id: int
    supplier_id: int
    supplier_name: str
    name: str
    details: str
    quantity: Decimal
    price: Decimal
    currency: Currency
    photo_key: str | None
    created_at: datetime
    # None = no payment request has ever included this product yet
    requested_amount: Decimal | None = None
    paid_amount: Decimal | None = None
    # Logistics rollup: shipped counts every non-cancelled shipment, accepted only
    # the received ones; both are 0 for a product that was never shipped.
    shipped_quantity: Decimal = Decimal("0")
    accepted_quantity: Decimal = Decimal("0")
    shipments: list[ProductShipmentOut] = []

    model_config = {"from_attributes": True}
