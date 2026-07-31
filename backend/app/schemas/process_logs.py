from pydantic import BaseModel


class LogSourceOut(BaseModel):
    name: str
    container: str
    state: str
    image: str


class LogSourcesOut(BaseModel):
    items: list[LogSourceOut]
    available: bool
    detail: str | None = None
    levels: list[str] | None = None


class LogLineOut(BaseModel):
    ts: str | None = None
    level: str
    text: str


class ProcessLogsOut(BaseModel):
    source: str
    lines: list[LogLineOut]
    count: int
    truncated: bool
