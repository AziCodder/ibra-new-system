from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TelegramGroup(Base):
    """A Telegram group/supergroup chat the bot has been added to."""

    __tablename__ = "telegram_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    # False once the bot is removed from the chat: nothing can be delivered there
    # anymore, but the admin's client links survive until the bot is added back.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClientTelegramGroup(Base):
    """An admin's decision to send client_id's notifications to group_id.

    Both FKs cascade — a membership row has no meaning once either side is
    gone, same reasoning as PaymentRequestItem.payment_request_id's existing
    ondelete="CASCADE" (contrast with Order.client_id, which is RESTRICT
    because an order must never silently vanish).
    """

    __tablename__ = "client_telegram_groups"
    __table_args__ = (
        UniqueConstraint("client_id", "group_id", name="uix_client_telegram_groups_client_group"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"))
    group_id: Mapped[int] = mapped_column(ForeignKey("telegram_groups.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
