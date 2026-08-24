from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BackupRunOut(BaseModel):
    id: int
    kind: Literal["hourly", "daily", "manual"]
    label: str
    title: str
    permanent: bool
    status: Literal["running", "ok", "failed"]
    object_key: str
    size: int
    sha256: str
    copies: int
    primary_state: str
    mirror_state: str
    stored_locally: bool
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int
    error: str
    node: str
    verified_at: datetime | None
    verify_status: str | None
    verify_detail: str
    restored_at: datetime | None
    restore_status: str | None
    restore_detail: str
    expires_at: datetime | None


class BackupSummaryOut(BaseModel):
    enabled: bool
    retention_days: int
    storage: str  # где лежат копии: "два S3" / "только диск сервера"
    hourly: dict | None
    daily: dict | None
    manual: dict | None
    verify: dict | None


class BackupListOut(BaseModel):
    summary: BackupSummaryOut
    items: list[BackupRunOut]


class BackupCreateIn(BaseModel):
    name: str = Field(default="", max_length=200, description="имя ручной копии")


class BackupActionOut(BaseModel):
    status: str
    id: int | None = None
    title: str | None = None
    detail: str | None = None
