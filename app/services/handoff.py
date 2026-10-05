from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Customer, CustomerStudent, Handoff


async def handoff_lead(db: AsyncSession, lead) -> dict:
    """Produce the TeacherOS StudentCreate payload for a won lead and record it."""
    if lead.stage != "won":
        raise ValueError("lead must be in won stage before handoff")

    lead_id = lead.id
    existing = (
        await db.execute(
            select(Handoff).where(Handoff.lead_id == lead_id, Handoff.id.is_not(None))
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ValueError("lead already handed off")

    customer_id = lead.customer_id
    customer = await db.get(Customer, customer_id)
    student = (
        await db.execute(
            select(CustomerStudent).where(
                CustomerStudent.customer_id == customer_id,
                CustomerStudent.id.is_not(None),
            )
        )
    ).scalars().first()

    payload = {
        "name": (student.name if student and student.name else f"{customer.name}的孩子"),
        "grade": student.grade if student else "",
        "subject": student.subject if student else "",
        "current_score": student.current_score if student else None,
        "target_score": student.target_score if student else None,
        "teacher_note": f"来源: {customer.source}；预算: {lead.budget if lead.budget else '未确认'}",
    }
    db.add(Handoff(lead_id=lead_id, payload=payload))
    await db.commit()
    return payload
