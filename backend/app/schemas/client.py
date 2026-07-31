from pydantic import BaseModel, Field


class ClientCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    description: str = ""
    telegram_group_link: str = Field(default="", max_length=255)
    telegram_chat_id: str = Field(default="", max_length=64)


class ClientUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    telegram_group_link: str | None = Field(default=None, max_length=255)
    telegram_chat_id: str | None = Field(default=None, max_length=64)


class ClientOut(BaseModel):
    id: int
    code: str
    full_name: str
    description: str
    telegram_group_link: str
    telegram_chat_id: str
    telegram_groups: list[str] = []

    model_config = {"from_attributes": True}
