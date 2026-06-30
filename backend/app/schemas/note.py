from datetime import datetime

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    text: str = Field(min_length=1)


class NoteOut(BaseModel):
    id: int
    order_id: int
    author_id: int
    author_name: str
    text: str
    created_at: datetime

    model_config = {"from_attributes": True}
