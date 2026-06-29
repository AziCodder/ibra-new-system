from pydantic import BaseModel

from app.models.user import UserRole


class UserCreate(BaseModel):
    login: str
    password: str
    role: UserRole = UserRole.manager
    full_name: str = ""


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = None


class UserOut(BaseModel):
    id: int
    login: str
    role: UserRole
    full_name: str
    is_active: bool

    model_config = {"from_attributes": True}
