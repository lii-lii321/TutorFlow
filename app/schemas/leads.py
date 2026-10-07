from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    stage: str
    intent: str
    budget: float | None
    next_action: str
    last_contact_at: datetime | None
    closed_reason: str
    updated_at: datetime


class LeadUpdate(BaseModel):
    intent: str | None = Field(default=None, pattern="^(high|mid|low)$")
    next_action: str | None = Field(default=None, max_length=256)
    budget: float | None = Field(default=None, gt=0)
    closed_reason: str | None = Field(default=None, max_length=256)


class TransitionIn(BaseModel):
    to_stage: str = Field(pattern="^(new|contacted|qualified|trial|won|lost)$")
    reason: str = Field(default="", max_length=256)


class LeadEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_stage: str
    to_stage: str
    reason: str
    created_at: datetime


class LeadDetailOut(LeadOut):
    events: list[LeadEventOut] = []
