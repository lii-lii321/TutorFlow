from datetime import timedelta

from app.models import Customer, Lead, LeadEvent
from app.services import analytics
from app.utils.clock import utcnow


async def seed_funnel(db):
    now = utcnow()

    won_customer = Customer(name="成交", source="朋友介绍")
    lost_customer = Customer(name="流失", source="抖音")
    early_customer = Customer(name="早期", source="朋友介绍")
    db.add_all([won_customer, lost_customer, early_customer])
    await db.flush()

    won_lead = Lead(customer_id=won_customer.id, stage="won", intent="high", budget=200.0)
    lost_lead = Lead(customer_id=lost_customer.id, stage="lost", intent="mid", budget=150.0)
    early_lead = Lead(
        customer_id=early_customer.id, stage="contacted", intent="high",
        last_contact_at=now - timedelta(days=1),
    )
    db.add_all([won_lead, lost_lead, early_lead])
    await db.flush()

    won_path = [("new", "contacted"), ("contacted", "qualified"), ("qualified", "trial"), ("trial", "won")]
    lost_path = [("new", "contacted"), ("contacted", "qualified"), ("qualified", "trial"), ("trial", "lost")]
    for lead, path in ((won_lead, won_path), (lost_lead, lost_path)):
        for from_stage, to_stage in path:
            db.add(LeadEvent(lead_id=lead.id, from_stage=from_stage, to_stage=to_stage))
    await db.commit()
    return won_lead, lost_lead, early_lead


async def test_funnel_counts_and_win_rate(client, db):
    await seed_funnel(db)
    data = await analytics.summary(db)

    assert data["stage_counts"]["won"] == 1
    assert data["stage_counts"]["lost"] == 1
    assert data["stage_counts"]["contacted"] == 1
    assert data["total_leads"] == 3
    assert data["win_rate"] == 0.5
    assert data["conversions"]["qualified_to_trial"] == 2
    assert data["conversions"]["trial_to_won"] == 1
    assert data["conversions"]["contacted_to_qualified"] == 2


async def test_avg_budget_only_counts_active_stages(client, db):
    await seed_funnel(db)
    data = await analytics.summary(db)
    assert data["avg_budget"] == 200.0


async def test_sources_breakdown(client, db):
    await seed_funnel(db)
    data = await analytics.summary(db)
    assert data["sources"]["朋友介绍"] == {"leads": 2, "won": 1}
    assert data["sources"]["抖音"] == {"leads": 1, "won": 0}


async def test_analytics_api_endpoint(client, db):
    await seed_funnel(db)
    resp = await client.get("/analytics/summary")
    assert resp.status_code == 200
    assert resp.json()["win_rate"] == 0.5
