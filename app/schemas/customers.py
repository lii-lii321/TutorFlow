from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    phone: str = ""
    source: str = "unknown"
    note: str = ""


class CustomerUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    source: str | None = None
    note: str | None = None


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    source: str
    note: str
    created_at: datetime


class CustomerStudentCreate(BaseModel):
    name: str = ""
    grade: str = ""
    subject: str = ""
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
