from datetime import datetime

from pydantic import BaseModel, Field


class LogisticsCommentCreate(BaseModel):
    text: str = Field(min_length=1)


class LogisticsCommentOut(BaseModel):
    id: int
    logistics_id: int
    author_id: int
    author_name: str
    text: str
    created_at: datetime

    model_config = {"from_attributes": True}
