import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LogisticsStatus(enum.StrEnum):
    in_transit = "in_transit"
    accepted = "accepted"
    cancelled = "cancelled"


class Logistics(Base):
    __tablename__ = "logistics"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    tracking: Mapped[str] = mapped_column(String(255), default="")
    ship_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    invoice_file_key: Mapped[str | None] = mapped_column(String(255), default=None)
    details: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[LogisticsStatus] = mapped_column(
        Enum(LogisticsStatus, name="logistics_status"), default=LogisticsStatus.in_transit
    )
    received_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    expense_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), default=None)
    currency: Mapped[str | None] = mapped_column(String(10), default=None)
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), default=None)
    acceptance_note: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
