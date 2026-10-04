from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Customer, CustomerStudent, FollowUp, Lead
from app.utils.clock import utcnow

STAGE_WEIGHT = {"new": 0.20, "contacted": 0.50, "qualified": 0.70, "trial": 0.90, "won": 0.10, "lost": 0.05}
INTENT_WEIGHT = {"high": 0.30, "mid": 0.15, "low": 0.05}
IDLE_CAP_DAYS = 14

SUGGESTED_ACTION = {
    "new": "首次电话/微信联系，了解具体需求",
    "contacted": "发送课程方案与价格说明",
    "qualified": "安排试听课时间",
    "trial": "试听后48小时内跟进反馈",
    "won": "确认开课时间与课表",
    "lost": "隔月回访",
}

MESSAGE_TEMPLATES = {
    "new": "{customer}您好，看到您之前咨询过{subject}辅导。可以先给孩子做一次免费学情诊断，我再给您针对性的提升方案，您看周几方便？",
    "contacted": "{customer}您好，上次沟通后我整理了一份课程计划（每周2次，每次90分钟，前期重点补薄弱模块），您看什么时候方便细聊？",
    "qualified": "{customer}您好，试听时间帮您约在周六上午可以吗？课上我会评估孩子的薄弱点，课后给您一份书面反馈。",
    "trial": "{customer}您好，试听后孩子的情况我做了记录：主要薄弱点已定位，配套练习也准备好了。如果觉得合适这周就可以排课，有任何顾虑直接和我说。",
    "won": "{customer}您好，课程已排好，课前我会发预习内容，课后每次都会给您反馈。有问题随时找我。",
    "lost": "{customer}您好，好久没联系了，最近孩子学习状态如何？有需要随时找我。",
}


def score_lead(lead: Lead, now=None) -> tuple:
    now = now or utcnow()
    reference = lead.last_contact_at or lead.updated_at
    idle_days = max(0, (now - reference).days) if reference else 0
    idle_component = min(idle_days, IDLE_CAP_DAYS) / IDLE_CAP_DAYS * 0.5
    total = STAGE_WEIGHT.get(lead.stage, 0.1) + INTENT_WEIGHT.get(lead.intent, 0.15) + idle_component
    if lead.stage == "trial" and idle_days >= 1:
        total += 0.2

    reasons = []
    if lead.stage == "new":
        reasons.append("新线索待首次联系")
    if idle_days >= 1:
        reasons.append(f"{idle_days}天未跟进")
    if lead.stage == "trial" and idle_days >= 1:
        reasons.append("试听后黄金跟进期")
    if lead.intent == "high" and idle_days >= 2:
        reasons.append("高意向客户，建议尽快回复")
    return round(total, 3), "；".join(reasons) or "保持联系"


def build_message(lead: Lead, customer, student=None) -> str:
    template = MESSAGE_TEMPLATES.get(lead.stage, MESSAGE_TEMPLATES["contacted"])
    subject = student.subject if student and student.subject else "文化课"
    return template.format(customer=customer.name, subject=subject)


async def generate_daily_followups(db: AsyncSession, now=None, top_n: int = 5) -> list:
    now = now or utcnow()
    leads = (await db.scalars(select(Lead))).all()
    scored = sorted(
        ((score_lead(lead, now), lead) for lead in leads),
        key=lambda item: item[0][0],
        reverse=True,
    )

    pending_ids = {
        row.lead_id
        for row in (
            await db.execute(
                select(FollowUp).where(FollowUp.status == "pending", FollowUp.done_at.is_(None))
            )
        ).scalars().all()
    }

    created = []
    for (value, reason), lead in scored:
        if len(created) >= top_n:
            break
        if lead.id in pending_ids or lead.stage in ("won", "lost"):
            continue
        lead_customer_id = lead.customer_id
        customer = await db.get(Customer, lead_customer_id)
        student = (
            await db.execute(
                select(CustomerStudent).where(
                    CustomerStudent.customer_id == lead_customer_id,
                    CustomerStudent.id.is_not(None),
                )
            )
        ).scalars().first()
        followup = FollowUp(
            lead_id=lead.id,
            reason=reason,
            suggested_action=SUGGESTED_ACTION.get(lead.stage, "保持联系"),
            suggested_message=build_message(lead, customer, student),
            score=value,
        )
        db.add(followup)
        created.append(followup)
    await db.commit()
    return created
