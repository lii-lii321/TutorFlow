from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Customer, FollowUp, Lead
from app.schemas.followup import FollowUpOut
from app.services import followup_engine
from app.utils.clock import utcnow

router = APIRouter(prefix="/followups", tags=["followups"])


async def enrich_with_lead_context(
    db: AsyncSession, followups: list[FollowUp]
) -> list[FollowUpOut]:
    """Attach customer name and lead stage so consumers know who to contact."""
    lead_ids = {followup.lead_id for followup in followups}
    name_by_lead: dict[int, str | None] = {}
    stage_by_lead: dict[int, str | None] = {}
    if lead_ids:
        leads_map = {
            lead.id: lead
            for lead in (
                await db.execute(
                    select(Lead).where(Lead.id.in_(lead_ids))
                )
            ).scalars().all()
        }
        customer_ids = {lead.customer_id for lead in leads_map.values()}
        customers_map = {
            customer.id: customer.name
            for customer in (
                await db.execute(
                    select(Customer).where(Customer.id.in_(customer_ids))
                )
            ).scalars().all()
        }
        name_by_lead = {
            lead_id: customers_map.get(lead.customer_id) for lead_id, lead in leads_map.items()
        }
        stage_by_lead = {lead_id: lead.stage for lead_id, lead in leads_map.items()}
    return [
        FollowUpOut.model_validate(followup).model_copy(
            update={
                "customer_name": name_by_lead.get(followup.lead_id),
                "lead_stage": stage_by_lead.get(followup.lead_id),
            }
        )
        for followup in followups
    ]


@router.post("/generate", response_model=list[FollowUpOut])
async def generate_followups(top_n: int = 5, db: AsyncSession = Depends(get_db)):
    created = await followup_engine.generate_daily_followups(
        db, now=utcnow(), top_n=max(1, min(top_n, 20))
    )
    return await enrich_with_lead_context(db, created)


@router.get("", response_model=list[FollowUpOut])
async def list_followups(status: str = "pending", db: AsyncSession = Depends(get_db)):
    query = select(FollowUp).order_by(FollowUp.score.desc())
    if status != "all":
        query = query.where(FollowUp.status == status)
    followups = list((await db.execute(query)).scalars().all())
    return await enrich_with_lead_context(db, followups)


@router.patch("/{followup_id}/done", response_model=FollowUpOut)
async def mark_done(followup_id: int, db: AsyncSession = Depends(get_db)):
    followup = await db.get(FollowUp, followup_id)
    if followup is None:
        raise HTTPException(status_code=404, detail="followup not found")
    if followup.status != "pending":
        raise HTTPException(status_code=409, detail="only pending followups can be marked done")
    followup.status = "done"
    followup.done_at = utcnow()
    await db.commit()
    await db.refresh(followup)
    return (await enrich_with_lead_context(db, [followup]))[0]
