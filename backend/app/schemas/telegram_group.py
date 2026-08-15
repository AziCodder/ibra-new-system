from datetime import datetime

from pydantic import BaseModel


class TelegramGroupOut(BaseModel):
    """A chat as a delivery target — what the notify dialogs pick from."""

    group_id: int
    chat_id: str
    title: str

    model_config = {"from_attributes": True}


class TelegramGroupAdminOut(BaseModel):
    """A chat as the admin sees it: who it serves, and whether the bot is still in it."""

    id: int
    chat_id: str
    title: str
    is_active: bool
    client_ids: list[int]
    created_at: datetime


class TelegramGroupClientsIn(BaseModel):
    """The full set of clients this chat serves — not a delta."""

    client_ids: list[int]
