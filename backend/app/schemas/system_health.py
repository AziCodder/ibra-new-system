from datetime import datetime
from typing import Literal

from pydantic import BaseModel

HealthStatus = Literal["ok", "warn", "down"]


class HealthServiceOut(BaseModel):
    name: str
    label: str
    status: HealthStatus
    latency_ms: int | None = None
    detail: str | None = None


class HealthProbeOut(BaseModel):
    name: str
    kind: Literal["page", "api"]
    status: HealthStatus
    status_code: int | None = None
    latency_ms: int | None = None
    detail: str | None = None


class HealthReportOut(BaseModel):
    enabled: bool
    overall: HealthStatus
    services: list[HealthServiceOut]
    pages: list[HealthProbeOut]
    checked_at: datetime
