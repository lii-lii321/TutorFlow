from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Customer, CustomerStudent, Lead
from app.services import state_machine
from app.services.parser import parse_message_smart
from app.utils.clock import utcnow

NEXT_ACTION_BY_STAGE = {
    "new": "首次联系，了解具体需求",
    "contacted": "发送课程方案与价格说明",
    "qualified": "安排试听课时间",
    "trial": "试听后48小时内跟进反馈",
    "won": "确认开课时间与课表",
    "lost": "隔月回访",
}


async def get_or_create_lead(db: AsyncSession, customer_id: int) -> Lead:
    lead = (
        await db.execute(
            select(Lead).where(Lead.customer_id == customer_id, Lead.stage.in_(state_machine.STAGES))
        )
    ).scalar_one_or_none()
    if lead is None:
        lead = Lead(customer_id=customer_id, next_action=NEXT_ACTION_BY_STAGE["new"])
        db.add(lead)
        await db.flush()
    return lead


async def get_or_create_student(db: AsyncSession, customer_id: int) -> CustomerStudent:
    student = (
        await db.execute(
            select(CustomerStudent).where(
                CustomerStudent.customer_id == customer_id,
                CustomerStudent.id.is_not(None),
            )
        )
    ).scalar_one_or_none()
    if student is None:
        student = CustomerStudent(customer_id=customer_id)
        db.add(student)
        await db.flush()
    return student


async def ingest_conversation(
    db: AsyncSession,
    customer: Customer,
    content: str,
    direction: str = "in",
    occurred_at=None,
) -> dict:
    extraction = await parse_message_smart(content)
    happened_at = occurred_at or utcnow()
    customer_id = customer.id
    student = await get_or_create_student(db, customer_id)
    lead = await get_or_create_lead(db, customer_id)

    fields = extraction.fields
    if fields.get("grade"):
        student.grade = fields["grade"]
    if fields.get("subject"):
        student.subject = fields["subject"]
    if fields.get("current_score") is not None:
        student.current_score = fields["current_score"]
    if fields.get("target_score") is not None:
        student.target_score = fields["target_score"]

    if fields.get("budget") is not None:
        lead.budget = fields["budget"]
    lead.intent = extraction.intent
    if direction == "in":
        lead.last_contact_at = happened_at
    lead.next_action = NEXT_ACTION_BY_STAGE[lead.stage]

    auto_events = []
    if direction == "in" and lead.stage == "new":
        event = state_machine.build_transition_event(lead, "contacted", reason="收到客户咨询消息")
        db.add(event)
        auto_events.append({"from": event.from_stage, "to": event.to_stage, "reason": event.reason})

    conversation = Conversation(
        customer_id=customer_id,
        direction=direction,
        content=content,
        occurred_at=happened_at,
        extracted={
            **fields,
            "intent": extraction.intent,
            "confidence": extraction.confidence,
            "missing": extraction.missing,
        },
        parser=extraction.parser,
    )
    db.add(conversation)
    await db.commit()
    return {
        "conversation": conversation,
        "lead": lead,
        "student": student,
        "extraction": extraction,
        "auto_events": auto_events,
    }
