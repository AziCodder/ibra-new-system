import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
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
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    tracking: Mapped[str | None] = mapped_column(String(255), default=None, nullable=True, unique=True)
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


class LogisticsItem(Base):
    """One product line of a shipment — a shipment carries one or more of these.

    Status, tracking and the acceptance figures live on the parent Logistics row:
    a shipment is shipped and accepted as a whole, never line by line.
    """

    __tablename__ = "logistics_items"
    __table_args__ = (
        # One line per product per shipment — two quantities for the same product
        # in one shipment are always a mistake, and would break the per-product
        # "already shipped" rollups.
        UniqueConstraint("logistics_id", "product_id", name="uq_logistics_items_logistics_product"),
        Index("ix_logistics_items_product", "product_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    logistics_id: Mapped[int] = mapped_column(ForeignKey("logistics.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
