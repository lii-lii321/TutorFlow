from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.clock import utcnow


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    direction: Mapped[str] = mapped_column(String(8), default="in")
    content: Mapped[str] = mapped_column(String(4096))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    extracted: Mapped[dict] = mapped_column(JSON, default=dict)
    parser: Mapped[str] = mapped_column(String(16), default="rules")
