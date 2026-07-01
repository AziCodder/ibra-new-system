import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NotificationStatus(enum.StrEnum):
    sent = "sent"
    failed = "failed"


class NotificationLog(Base):
    """Persisted outcome of every attempted outbound Telegram notification.

    A row is written after each delivery attempt so failures are not only
    logged but visible/queryable (the "не доставлено" indicator of Phase 11.5).
    The token-less no-op path (no bot configured) writes nothing.
    """

    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    target: Mapped[str] = mapped_column(String(255), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, name="notification_status")
    )
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
