import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PaymentRequestPriority(enum.StrEnum):
    low = "low"
    normal = "normal"
    urgent = "urgent"


class PaymentRequest(Base):
    __tablename__ = "payment_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    requisites: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[PaymentRequestPriority] = mapped_column(
        Enum(PaymentRequestPriority, name="payment_request_priority"), default=PaymentRequestPriority.normal
    )
    file_keys: Mapped[list[str]] = mapped_column(ARRAY(String(255)), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaymentRequestItem(Base):
    __tablename__ = "payment_request_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_request_id: Mapped[int] = mapped_column(ForeignKey("payment_requests.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
