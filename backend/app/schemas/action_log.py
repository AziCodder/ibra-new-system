from datetime import datetime

from pydantic import BaseModel


class ActionLogOut(BaseModel):
    id: int
    actor_id: int
    actor_name: str
    action: str
    entity_type: str
    entity_id: int
    details: str
    created_at: datetime

    model_config = {"from_attributes": True}
