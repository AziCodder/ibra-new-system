from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    name: Mapped[str] = mapped_column(String(255))
    details: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    # Units of the order's currency per 1 unit of `currency` — the direction the
    # form asks for ("1 CNY = 11.5 RUB" -> 11.5), so converting multiplies. Always
    # 1 when the product is priced in its order's currency. For a foreign currency
    # it is optional (NULL = not given) and only feeds the "total in the order's
    # currency" preview: profit values purchases at each payment's own rate
    # (profit.py). No default on purpose — with one, SQLAlchemy would write it in
    # place of an explicit None.
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
    photo_key: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
