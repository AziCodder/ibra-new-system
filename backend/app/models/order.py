import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OrderStatus(enum.StrEnum):
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_client_created", "client_id", "created_at"),
        Index("ix_orders_client_status", "client_id", "status"),
        Index("ix_orders_manager_created", "manager_id", "created_at"),
        Index("ix_orders_status", "status"),
        Index("ix_orders_completed_at", "completed_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    manager_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus, name="order_status"), default=OrderStatus.in_progress)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    details: Mapped[str] = mapped_column(Text, default="")
    file_keys: Mapped[list[str]] = mapped_column(ARRAY(String(255)), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Snapshot fields — populated by snapshot_order_metrics() when is_ready
    profit_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    processing_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_income: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    profit_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
