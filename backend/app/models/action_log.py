from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ActionLog(Base):
    """Audit trail of key operations (creation / status change / acceptance).

    Written in the same transaction as the operation it records, so the log is
    consistent with the data. Queryable by admins for dispute investigation
    (Phase 12.2). Actor and timestamp follow the same author+date pattern as
    other records (see test_audit_author_date).
    """

    __tablename__ = "action_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    # No cascade: an audit trail must survive even if the actor is removed
    # (matches the migration's plain FK). Users are deactivated, not deleted.
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[int] = mapped_column(Integer)
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
