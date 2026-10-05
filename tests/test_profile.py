from datetime import timedelta

from app.models import Conversation, Customer, Lead, LeadEvent
from app.services.profile import customer_profile
from app.utils.clock import utcnow


async def seed_profile_scenario(
    db,
    *,
    inbound_offset_days: float,
    trial_offset_days: float | None,
    budgets: list,
):
    now = utcnow()
    customer = Customer(name="画像家长", source="朋友介绍")
    db.add(customer)
    await db.flush()
    lead = Lead(customer_id=customer.id, stage="trial", intent="high")
    db.add(lead)
    await db.flush()
    if trial_offset_days is not None:
        db.add(
            LeadEvent(
                lead_id=lead.id,
                from_stage="qualified",
                to_stage="trial",
                created_at=now + timedelta(days=trial_offset_days),
            )
        )
    for i, budget in enumerate(budgets):
        db.add(
            Conversation(
                customer_id=customer.id,
                direction="in",
                content=f"咨询消息{i}",
                occurred_at=now + timedelta(days=inbound_offset_days + i * 0.5),
                extracted={"budget": budget} if budget is not None else {},
            )
        )
    await db.commit()
    await db.refresh(customer)
    return customer


async def test_decision_speed_days_positive(db):
    customer = await seed_profile_scenario(
        db, inbound_offset_days=-3, trial_offset_days=-1, budgets=[150]
    )
    profile = await customer_profile(db, customer)
    assert profile["decision_speed_days"] == 2.0


async def test_decision_speed_days_clamped_non_negative(db):
    customer = await seed_profile_scenario(
        db, inbound_offset_days=1, trial_offset_days=-1, budgets=[150]
    )
    profile = await customer_profile(db, customer)
    assert profile["decision_speed_days"] == 0.0


async def test_decision_speed_days_none_without_trial_event(db):
    customer = await seed_profile_scenario(
        db, inbound_offset_days=-3, trial_offset_days=None, budgets=[150]
    )
    profile = await customer_profile(db, customer)
    assert profile["decision_speed_days"] is None


async def test_price_sensitivity_branches(db):
    falling = await seed_profile_scenario(
        db, inbound_offset_days=-2, trial_offset_days=None, budgets=[200, 150]
    )
    assert (await customer_profile(db, falling))["price_sensitivity"] == "high"

    flat = await seed_profile_scenario(
        db, inbound_offset_days=-2, trial_offset_days=None, budgets=[150, 150]
    )
    assert (await customer_profile(db, flat))["price_sensitivity"] == "mid"

    single = await seed_profile_scenario(
        db, inbound_offset_days=-2, trial_offset_days=None, budgets=[150]
    )
    assert (await customer_profile(db, single))["price_sensitivity"] == "unknown"


async def test_profile_api_exposes_metrics(client, db):
    customer = await seed_profile_scenario(
        db, inbound_offset_days=-3, trial_offset_days=-1, budgets=[200, 150]
    )
    resp = await client.get(f"/customers/{customer.id}/profile")
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision_speed_days"] == 2.0
    assert body["price_sensitivity"] == "high"
    assert body["budget_history"][0]["budget"] == 200
