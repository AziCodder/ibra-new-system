from datetime import datetime

from pydantic import BaseModel

from app.models.notification_log import NotificationStatus


class NotificationLogOut(BaseModel):
    id: int
    target: str
    message: str
    status: NotificationStatus
    error: str
    created_at: datetime

    model_config = {"from_attributes": True}
