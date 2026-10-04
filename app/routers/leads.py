from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Lead, LeadEvent
from app.schemas.leads import LeadDetailOut, LeadOut, LeadUpdate, TransitionIn
from app.services import state_machine

router = APIRouter(prefix="/leads", tags=["leads"])


async def get_lead_or_404(db: AsyncSession, lead_id: int) -> Lead:
    lead = await db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="lead not found")
    return lead


@router.get("", response_model=list[LeadOut])
async def list_leads(stage: str | None = None, intent: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(Lead).order_by(Lead.id)
    if stage:
        query = query.where(Lead.stage == stage)
    if intent:
        query = query.where(Lead.intent == intent)
    return list((await db.execute(query)).scalars().all())


@router.get("/{lead_id}", response_model=LeadDetailOut)
async def get_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    lead = await get_lead_or_404(db, lead_id)
    events = (
        await db.scalars(
            select(LeadEvent)
            .where(LeadEvent.lead_id == lead.id)
            .order_by(LeadEvent.created_at)
        )
    ).all()
    return LeadDetailOut.model_validate(lead).model_copy(update={"events": list(events)})


@router.patch("/{lead_id}", response_model=LeadOut)
async def update_lead(lead_id: int, payload: LeadUpdate, db: AsyncSession = Depends(get_db)):
    lead = await get_lead_or_404(db, lead_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)
    await db.commit()
    await db.refresh(lead)
    return lead


@router.post("/{lead_id}/transition", response_model=LeadOut)
async def transition_lead(lead_id: int, payload: TransitionIn, db: AsyncSession = Depends(get_db)):
    lead = await get_lead_or_404(db, lead_id)
    try:
        event = state_machine.build_transition_event(lead, payload.to_stage, reason=payload.reason)
    except state_machine.InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.add(event)
    await db.commit()
    await db.refresh(lead)
    return lead
