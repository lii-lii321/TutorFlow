from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FollowUpOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lead_id: int
    reason: str
    suggested_action: str
    suggested_message: str
    score: float
    status: str
    created_at: datetime
    done_at: datetime | None = None
