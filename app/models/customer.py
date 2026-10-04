from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.clock import utcnow


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    phone: Mapped[str] = mapped_column(String(32), default="")
    source: Mapped[str] = mapped_column(String(32), default="unknown")
    note: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    students: Mapped[list["CustomerStudent"]] = relationship(back_populates="customer")


class CustomerStudent(Base):
    __tablename__ = "customer_students"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    grade: Mapped[str] = mapped_column(String(32), default="")
    subject: Mapped[str] = mapped_column(String(32), default="")
    current_score: Mapped[int | None] = mapped_column(default=None)
    target_score: Mapped[int | None] = mapped_column(default=None)

    customer: Mapped["Customer"] = relationship(back_populates="students")
