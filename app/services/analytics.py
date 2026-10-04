from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Customer, Lead, LeadEvent
from app.services.state_machine import STAGES

BUDGET_STAGES = ["qualified", "trial", "won"]


async def summary(db: AsyncSession) -> dict:
    leads = (await db.scalars(select(Lead))).all()
    events = (await db.scalars(select(LeadEvent))).all()
    customers = (await db.scalars(select(Customer))).all()

    stage_counts = {stage: 0 for stage in STAGES}
    for lead in leads:
        stage_counts[lead.stage] = stage_counts.get(lead.stage, 0) + 1

    won_leads = [lead for lead in leads if lead.stage == "won"]
    lost_leads = [lead for lead in leads if lead.stage == "lost"]
    closed = len(won_leads) + len(lost_leads)

    budgeted = [
        lead.budget
        for lead in leads
        if lead.stage in BUDGET_STAGES and lead.budget is not None
    ]

    conversions = {}
    for prev_stage, next_stage in (
        ("contacted", "qualified"),
        ("qualified", "trial"),
        ("trial", "won"),
        ("contacted", "trial"),
    ):
        conversions[f"{prev_stage}_to_{next_stage}"] = len({
            event.lead_id for event in events
            if event.from_stage == prev_stage and event.to_stage == next_stage
        })

    sources = {}
    customer_by_id = {customer.id: customer for customer in customers}
    for lead in leads:
        customer = customer_by_id.get(lead.customer_id)
        source = customer.source if customer else "unknown"
        bucket = sources.setdefault(source, {"leads": 0, "won": 0})
        bucket["leads"] += 1
        if lead.stage == "won":
            bucket["won"] += 1

    total_leads = await db.scalar(select(func.count(Lead.id)).where(Lead.id.is_not(None), Lead.stage.in_(STAGES)))

    return {
        "stage_counts": stage_counts,
        "total_leads": total_leads or 0,
        "win_rate": round(len(won_leads) / closed, 4) if closed else None,
        "avg_budget": round(sum(budgeted) / len(budgeted), 2) if budgeted else None,
        "conversions": conversions,
        "sources": sources,
    }
