from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OrderCalculationParticipant(Base):
    """One person's share of a calculated order's profit."""

    __tablename__ = "order_calculation_participants"
    __table_args__ = (UniqueConstraint("order_id", "user_id", name="uq_order_calculation_participant"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    percent: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    # Fixed when the calculation is saved, in the order's currency.
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
