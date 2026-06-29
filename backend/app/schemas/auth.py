from pydantic import BaseModel

from app.models.user import UserRole


class LoginRequest(BaseModel):
    login: str
    password: str


class UserResponse(BaseModel):
    id: int
    login: str
    role: UserRole
    full_name: str
    is_active: bool

    model_config = {"from_attributes": True}
