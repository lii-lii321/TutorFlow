from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator


def to_naive_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    phone: str = Field(default="", max_length=32)
    source: str = Field(default="unknown", max_length=32)
    note: str = Field(default="", max_length=512)


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    source: str | None = Field(default=None, max_length=32)
    note: str | None = Field(default=None, max_length=512)


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    source: str
    note: str
    created_at: datetime


class CustomerStudentCreate(BaseModel):
    name: str = Field(default="", max_length=64)
    grade: str = Field(default="", max_length=32)
    subject: str = Field(default="", max_length=32)
    current_score: int | None = None
    target_score: int | None = None


class CustomerStudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    name: str
    grade: str
    subject: str
    current_score: int | None
    target_score: int | None


class ConversationIn(BaseModel):
    direction: str = Field(default="in", pattern="^(in|out)$")
    content: str = Field(min_length=1, max_length=4000)
    occurred_at: datetime | None = None

    @field_validator("occurred_at", mode="after")
    @classmethod
    def _normalize_occurred_at(cls, value):
        return to_naive_utc(value)


class ChatLogIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    occurred_at: datetime | None = None

    @field_validator("occurred_at", mode="after")
    @classmethod
    def _normalize_occurred_at(cls, value):
        return to_naive_utc(value)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    direction: str
    content: str
    occurred_at: datetime
    extracted: dict
    parser: str


class CustomerProfileOut(BaseModel):
    customer: CustomerOut
    students: list[CustomerStudentOut]
    lead_stage: str | None = None
    budget_history: list[dict]
    needs: list[str]
    price_sensitivity: str
    decision_speed_days: float | None = None
    conversation_count: int
