from pydantic import BaseModel, Field


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    contacts: str = ""
    details: str = ""


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    contacts: str | None = None
    details: str | None = None


class SupplierOut(BaseModel):
    id: int
    name: str
    contacts: str
    details: str

    model_config = {"from_attributes": True}
