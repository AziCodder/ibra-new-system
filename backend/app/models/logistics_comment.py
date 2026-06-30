from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LogisticsComment(Base):
    __tablename__ = "logistics_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    logistics_id: Mapped[int] = mapped_column(ForeignKey("logistics.id", ondelete="CASCADE"))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
