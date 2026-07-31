from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OrderSortPosition(Base):
    """Персональный порядок заказов для конкретного пользователя.

    Один пользователь перетаскивает карточки под себя — у остальных порядок
    не меняется. Используется только сортировкой sort_by=manual.
    """

    __tablename__ = "order_sort_positions"
    __table_args__ = (
        UniqueConstraint("user_id", "order_id", name="uq_order_sort_position_user_order"),
        Index("ix_order_sort_positions_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
