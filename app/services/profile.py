from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Customer, CustomerStudent, Lead, LeadEvent
from app.services.state_machine import STAGES


async def customer_profile(db: AsyncSession, customer: Customer) -> dict:
    customer_id = customer.id
    conversations = (
        await db.scalars(
            select(Conversation)
            .where(Conversation.customer_id == customer_id)
            .order_by(Conversation.occurred_at)
        )
    ).all()
    lead = (
        await db.scalars(
            select(Lead).where(Lead.customer_id == customer_id, Lead.stage.in_(STAGES))
        )
    ).first()
    events = (
        await db.scalars(
            select(LeadEvent)
            .where(LeadEvent.lead_id == (lead.id if lead else -1))
            .order_by(LeadEvent.created_at)
        )
    ).all()
    students = (
        await db.scalars(
            select(CustomerStudent).where(
                CustomerStudent.customer_id == customer_id,
                CustomerStudent.id.is_not(None),
            )
        )
    ).all()

    budget_history = [
        {"date": conv.occurred_at.isoformat(), "budget": conv.extracted.get("budget")}
        for conv in conversations
        if conv.extracted.get("budget") is not None
    ]
    needs: list = []
    for conv in conversations:
        for need in conv.extracted.get("needs", []):
            if need not in needs:
                needs.append(need)

    return {
        "customer": customer,
        "students": list(students),
        "lead_stage": lead.stage if lead else None,
        "budget_history": budget_history,
        "needs": needs,
        "price_sensitivity": _price_sensitivity(budget_history),
        "decision_speed_days": _decision_speed_days(conversations, events),
        "conversation_count": len(conversations),
    }


def _price_sensitivity(budget_history: list) -> str:
    budgets = [entry["budget"] for entry in budget_history]
    if len(budgets) < 2:
        return "unknown"
    if budgets[-1] < budgets[0]:
        return "high"
    if budgets[-1] > budgets[0]:
        return "low"
    return "mid"


def _decision_speed_days(conversations: list, events: list) -> float | None:
    inbound = [conv for conv in conversations if conv.direction == "in"]
    if not inbound:
        return None
    trial_events = [event for event in events if event.to_stage == "trial"]
    if not trial_events:
        return None
    delta = trial_events[0].created_at - inbound[0].occurred_at
    return round(max(delta.total_seconds(), 0) / 86400, 1)
