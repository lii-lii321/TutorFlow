from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Conversation, Customer, CustomerStudent, Lead
from app.schemas.customers import (
    ChatLogIn,
    ConversationIn,
    ConversationOut,
    CustomerCreate,
    CustomerOut,
    CustomerProfileOut,
    CustomerStudentCreate,
    CustomerStudentOut,
    CustomerUpdate,
)
from app.services import ingest, profile as profile_service
from app.services.state_machine import STAGES

router = APIRouter(prefix="/customers", tags=["customers"])


async def get_customer_or_404(db: AsyncSession, customer_id: int) -> Customer:
    customer = await db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return customer


async def get_lead_or_none(db: AsyncSession, customer_id: int) -> Lead | None:
    return (
        await db.execute(
            select(Lead).where(Lead.customer_id == customer_id, Lead.stage.in_(STAGES))
        )
    ).scalar_one_or_none()


@router.post("", response_model=CustomerOut, status_code=201)
async def create_customer(payload: CustomerCreate, db: AsyncSession = Depends(get_db)):
    customer = Customer(**payload.model_dump())
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer


@router.get("", response_model=list[CustomerOut])
async def list_customers(stage: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(Customer).order_by(Customer.id)
    if stage:
        query = query.join(Lead, Lead.customer_id == Customer.id).where(Lead.stage == stage)
    return list((await db.execute(query)).scalars().all())


@router.get("/{customer_id}", response_model=CustomerOut)
async def get_customer(customer_id: int, db: AsyncSession = Depends(get_db)):
    return await get_customer_or_404(db, customer_id)


@router.patch("/{customer_id}", response_model=CustomerOut)
async def update_customer(customer_id: int, payload: CustomerUpdate, db: AsyncSession = Depends(get_db)):
    customer = await get_customer_or_404(db, customer_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    await db.commit()
    await db.refresh(customer)
    return customer


@router.post("/{customer_id}/students", response_model=CustomerStudentOut, status_code=201)
async def add_student(customer_id: int, payload: CustomerStudentCreate, db: AsyncSession = Depends(get_db)):
    customer = await get_customer_or_404(db, customer_id)
    student = CustomerStudent(customer_id=customer.id, **payload.model_dump())
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


@router.post("/{customer_id}/conversations", status_code=201)
async def add_conversation(customer_id: int, payload: ConversationIn, db: AsyncSession = Depends(get_db)):
    customer = await get_customer_or_404(db, customer_id)
    result = await ingest.ingest_conversation(
        db, customer, payload.content, direction=payload.direction, occurred_at=payload.occurred_at
    )
    return {
        "conversation": ConversationOut.model_validate(result["conversation"]).model_dump(),
        "lead": {
            "id": result["lead"].id,
            "stage": result["lead"].stage,
            "intent": result["lead"].intent,
            "budget": result["lead"].budget,
            "next_action": result["lead"].next_action,
        },
        "extraction": {
            "fields": result["extraction"].fields,
            "missing": result["extraction"].missing,
            "intent": result["extraction"].intent,
            "confidence": result["extraction"].confidence,
            "parser": result["extraction"].parser,
        },
        "auto_events": result["auto_events"],
    }


@router.post("/{customer_id}/conversations/bulk")
async def bulk_ingest_chat_log(customer_id: int, payload: ChatLogIn, db: AsyncSession = Depends(get_db)):
    customer = await get_customer_or_404(db, customer_id)
    messages = ingest.parse_chat_log(payload.text)
    if not messages:
        raise HTTPException(status_code=422, detail="no messages parsed from text")
    happened_at = payload.occurred_at
    ingested = 0
    lead_stage = None
    auto_events_total = 0
    for message in messages:
        result = await ingest.ingest_conversation(
            db, customer, message["content"], direction=message["direction"], occurred_at=happened_at
        )
        ingested += 1
        lead_stage = result["lead"].stage
        auto_events_total += len(result["auto_events"])
    return {
        "ingested": ingested,
        "lead_stage": lead_stage,
        "auto_events_total": auto_events_total,
    }


@router.get("/{customer_id}/conversations", response_model=list[ConversationOut])
async def list_conversations(customer_id: int, db: AsyncSession = Depends(get_db)):
    await get_customer_or_404(db, customer_id)
    query = (
        select(Conversation)
        .where(Conversation.customer_id == customer_id)
        .order_by(Conversation.occurred_at)
    )
    return list((await db.execute(query)).scalars().all())


@router.get("/{customer_id}/profile", response_model=CustomerProfileOut)
async def customer_profile(customer_id: int, db: AsyncSession = Depends(get_db)):
    customer = await get_customer_or_404(db, customer_id)
    return await profile_service.customer_profile(db, customer)
