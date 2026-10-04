from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import FollowUp
from app.schemas.followup import FollowUpOut
from app.services import followup_engine
from app.utils.clock import utcnow

router = APIRouter(prefix="/followups", tags=["followups"])


@router.post("/generate", response_model=list[FollowUpOut])
async def generate_followups(top_n: int = 5, db: AsyncSession = Depends(get_db)):
    return await followup_engine.generate_daily_followups(db, now=utcnow(), top_n=max(1, min(top_n, 20)))


@router.get("", response_model=list[FollowUpOut])
async def list_followups(status: str = "pending", db: AsyncSession = Depends(get_db)):
    query = select(FollowUp).order_by(FollowUp.score.desc())
    if status != "all":
        query = query.where(FollowUp.status == status)
    return list((await db.execute(query)).scalars().all())


@router.patch("/{followup_id}/done", response_model=FollowUpOut)
async def mark_done(followup_id: int, db: AsyncSession = Depends(get_db)):
    followup = await db.get(FollowUp, followup_id)
    if followup is None:
        raise HTTPException(status_code=404, detail="followup not found")
    followup.status = "done"
    followup.done_at = utcnow()
    await db.commit()
    await db.refresh(followup)
    return followup
