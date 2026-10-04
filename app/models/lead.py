from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.clock import utcnow


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), unique=True, index=True)
    stage: Mapped[str] = mapped_column(String(16), default="new")
    intent: Mapped[str] = mapped_column(String(8), default="mid")
    budget: Mapped[float | None] = mapped_column(Float, default=None)
    next_action: Mapped[str] = mapped_column(String(256), default="")
    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    closed_reason: Mapped[str] = mapped_column(String(256), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class LeadEvent(Base):
    __tablename__ = "lead_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    from_stage: Mapped[str] = mapped_column(String(16))
    to_stage: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
