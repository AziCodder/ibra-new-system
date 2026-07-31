from pydantic import BaseModel


class TelegramGroupOut(BaseModel):
    group_id: int
    chat_id: str
    title: str

    model_config = {"from_attributes": True}
