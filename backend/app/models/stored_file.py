import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ReplicaState(enum.StrEnum):
    """Состояние копии файла в одном конкретном бакете."""

    ok = "ok"            # записан и подтверждён
    pending = "pending"  # ещё не записан, ждёт дозаливки фоновой задачей
    error = "error"      # запись сорвалась с ошибкой (текст — в last_error)
    missing = "missing"  # сверка не нашла объект там, где он должен быть
    disabled = "disabled"  # бакет не настроен (например, зеркала пока нет)


class StoredFile(Base):
    """Реестр файлов пользовательских вложений во внешнем хранилище.

    Нужен ровно для одного: знать, что где лежит, и уметь это доказать.
    Ключи файлов раскиданы по разным таблицам (``orders.file_keys``,
    ``products.photo_key``, …) и ничего не говорят о том, доехал ли файл до
    второго бакета. Здесь для каждого ключа хранится размер, SHA-256 и
    состояние каждой из двух копий — на этом строятся сверка бакетов,
    дозаливка отставших и показания вкладки «Хранилище» в админке.

    SHA-256 считается один раз при загрузке и дальше служит эталоном: копии
    сравниваются с ним, а не друг с другом, — иначе одинаково испорченные
    копии выглядели бы совпадающими.
    """

    __tablename__ = "stored_files"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), default="")
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")

    primary_state: Mapped[ReplicaState] = mapped_column(
        Enum(ReplicaState, name="replica_state"), default=ReplicaState.pending
    )
    mirror_state: Mapped[ReplicaState] = mapped_column(
        Enum(ReplicaState, name="replica_state"), default=ReplicaState.pending
    )
    last_error: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    replicated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Надгробие: файл удалён из приложения. Строка живёт, пока удаление не
    # подтверждено обоими бакетами, иначе «удалённый» файл тихо остался бы
    # лежать в зеркале.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def in_sync(self) -> bool:
        """Обе копии на месте (или зеркало сознательно отключено)."""
        return self.primary_state == ReplicaState.ok and self.mirror_state in (
            ReplicaState.ok,
            ReplicaState.disabled,
        )
