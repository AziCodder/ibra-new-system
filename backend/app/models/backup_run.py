import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.stored_file import ReplicaState


class BackupKind(enum.StrEnum):
    hourly = "hourly"  # временный: живёт 7 дней
    daily = "daily"    # постоянный: не удаляется никогда
    manual = "manual"  # запущен руками из админки


class BackupStatus(enum.StrEnum):
    running = "running"
    ok = "ok"
    failed = "failed"


class BackupRun(Base):
    """Журнал резервных копий: что, когда, куда и удалось ли развернуть.

    Строка создаётся до запуска ``pg_dump`` и закрывается по итогу, поэтому
    оборванный бэкап виден как ``running``, а не исчезает бесследно.

    ``verify_status`` — результат ночной проверки: дамп реально разворачивается
    в отдельную пустую базу. Бэкап, который никто ни разу не восстанавливал,
    не является бэкапом — он им только выглядит.
    """

    __tablename__ = "backup_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[BackupKind] = mapped_column(Enum(BackupKind, name="backup_kind"))
    # Имя, которое задал администратор при ручном создании. Автоматические
    # копии остаются без имени и показываются по дате.
    label: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[BackupStatus] = mapped_column(
        Enum(BackupStatus, name="backup_status"), default=BackupStatus.running
    )

    object_key: Mapped[str] = mapped_column(String(255), default="")
    local_path: Mapped[str] = mapped_column(String(500), default="")
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")

    primary_state: Mapped[ReplicaState] = mapped_column(
        Enum(ReplicaState, name="replica_state"), default=ReplicaState.pending
    )
    mirror_state: Mapped[ReplicaState] = mapped_column(
        Enum(ReplicaState, name="replica_state"), default=ReplicaState.pending
    )

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    node: Mapped[str] = mapped_column(String(100), default="")

    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verify_status: Mapped[BackupStatus | None] = mapped_column(
        Enum(BackupStatus, name="backup_status"), nullable=True
    )
    verify_detail: Mapped[str] = mapped_column(Text, default="")

    # Откат системы на эту копию: когда, чем закончился и что именно сделано.
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    restore_status: Mapped[BackupStatus | None] = mapped_column(
        Enum(BackupStatus, name="backup_status"), nullable=True
    )
    restore_detail: Mapped[str] = mapped_column(Text, default="")

    # Проставляется при чистке часовых копий по сроку хранения и при удалении
    # копии администратором. Суточные и ручные автоматика не трогает.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def stored_copies(self) -> int:
        return sum(1 for s in (self.primary_state, self.mirror_state) if s == ReplicaState.ok)

    @property
    def permanent(self) -> bool:
        """Постоянная копия: суточные и все ручные хранятся бессрочно."""
        return self.kind in (BackupKind.daily, BackupKind.manual)

    @property
    def title(self) -> str:
        return self.label or self.object_key.rsplit("/", 1)[-1]
