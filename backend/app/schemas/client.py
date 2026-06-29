from pydantic import BaseModel


class ClientCreate(BaseModel):
    code: str
    full_name: str
    description: str = ""
    telegram_group_link: str = ""


class ClientUpdate(BaseModel):
    full_name: str | None = None
    description: str | None = None
    telegram_group_link: str | None = None


class ClientOut(BaseModel):
    id: int
    code: str
    full_name: str
    description: str
    telegram_group_link: str

    model_config = {"from_attributes": True}
