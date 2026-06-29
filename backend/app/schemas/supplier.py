from pydantic import BaseModel


class SupplierCreate(BaseModel):
    name: str
    contacts: str = ""
    details: str = ""


class SupplierUpdate(BaseModel):
    name: str | None = None
    contacts: str | None = None
    details: str | None = None


class SupplierOut(BaseModel):
    id: int
    name: str
    contacts: str
    details: str

    model_config = {"from_attributes": True}
