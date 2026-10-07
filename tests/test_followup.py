from datetime import timedelta

from app.models import Customer, CustomerStudent, Lead
from app.services.followup_engine import generate_daily_followups, score_lead
from app.utils.clock import utcnow


async def seed_leads(db):
    now = utcnow()
    trial_customer = Customer(name="试听家长")
    new_customer = Customer(name="新家长")
    won_customer = Customer(name="成交家长")
    db.add_all([trial_customer, new_customer, won_customer])
    await db.flush()

    trial_lead = Lead(
        customer_id=trial_customer.id, stage="trial", intent="high",
        last_contact_at=now - timedelta(days=3),
    )
    new_lead = Lead(
        customer_id=new_customer.id, stage="new", intent="mid",
        last_contact_at=now,
    )
    won_lead = Lead(customer_id=won_customer.id, stage="won", intent="high")
    db.add_all([trial_lead, new_lead, won_lead])
    await db.commit()
    return now, trial_lead, new_lead, won_lead


async def test_score_orders_trial_high_first(client, db):
    now, trial_lead, new_lead, won_lead = await seed_leads(db)
    trial_value, trial_reason = score_lead(trial_lead, now)
    new_value, new_reason = score_lead(new_lead, now)
    assert trial_value > new_value
    assert "试听后黄金跟进期" in trial_reason
    assert "3天未跟进" in trial_reason


async def test_generate_ranks_excludes_won_and_dedupes(client, db):
    now, trial_lead, new_lead, won_lead = await seed_leads(db)

    created = await generate_daily_followups(db, now=now)
    assert len(created) == 2
    assert created[0].lead_id == trial_lead.id
    assert created[0].score > created[1].score
    assert "试听家长" in created[0].suggested_message
    assert created[1].reason

    again = await generate_daily_followups(db, now=now)
    assert again == []


async def test_done_followup_reopens_generation(client, db):
    now, trial_lead, new_lead, _ = await seed_leads(db)
    created = await generate_daily_followups(db, now=now)
    followup_id = created[0].id

    resp = await client.patch(f"/followups/{followup_id}/done")
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"

    regenerated = await generate_daily_followups(db, now=now)
    assert len(regenerated) == 1
    assert regenerated[0].lead_id == trial_lead.id


async def test_followup_api_listing(client, db):
    now, *_ = await seed_leads(db)
    await generate_daily_followups(db, now=now)

    pending = (await client.get("/followups")).json()
    assert len(pending) == 2
    assert pending[0]["score"] >= pending[1]["score"]

    resp = await client.post("/followups/generate", params={"top_n": 3})
    assert resp.status_code == 200
    assert resp.json() == []


async def seed_trial_lead(db):
    now = utcnow()
    customer = Customer(name="试听家长")
    db.add(customer)
    await db.flush()
    lead = Lead(
        customer_id=customer.id,
        stage="trial",
        intent="high",
        last_contact_at=now - timedelta(days=3),
    )
    db.add(lead)
    await db.commit()
    return now, lead


async def test_transition_to_lost_cancels_pending_followups(client, db):
    now, lead = await seed_trial_lead(db)
    created = await generate_daily_followups(db, now=now)
    assert len(created) == 1

    resp = await client.post(f"/leads/{lead.id}/transition", json={"to_stage": "lost", "reason": "预算不合"})
    assert resp.status_code == 200

    assert (await client.get("/followups")).json() == []
    cancelled = (await client.get("/followups", params={"status": "cancelled"})).json()
    assert [f["lead_id"] for f in cancelled] == [lead.id]
    assert cancelled[0]["suggested_action"] == "试听后48小时内跟进反馈"
    assert cancelled[0]["done_at"] is not None


async def test_backflow_from_lost_regenerates_followups(client, db):
    now, lead = await seed_trial_lead(db)
    await generate_daily_followups(db, now=now)
    resp = await client.post(f"/leads/{lead.id}/transition", json={"to_stage": "lost", "reason": "预算不合"})
    assert resp.status_code == 200

    resp = await client.post(f"/leads/{lead.id}/transition", json={"to_stage": "contacted", "reason": "客户回流"})
    assert resp.status_code == 200

    regenerated = await generate_daily_followups(db, now=now)
    assert [f.lead_id for f in regenerated] == [lead.id]
    assert regenerated[0].suggested_action == "发送课程方案与价格说明"


async def test_followup_responses_include_customer_identity(client, db):
    now, *_ = await seed_leads(db)

    generated = (await client.post("/followups/generate", params={"top_n": 5})).json()
    assert [item["customer_name"] for item in generated] == ["试听家长", "新家长"]
    assert [item["lead_stage"] for item in generated] == ["trial", "new"]

    listed = (await client.get("/followups")).json()
    assert listed[0]["customer_name"] == "试听家长"
    assert listed[0]["lead_stage"] == "trial"

    done = (await client.patch(f"/followups/{generated[0]['id']}/done")).json()
    assert done["customer_name"] == "试听家长"
    assert done["status"] == "done"


async def test_cancelled_followups_keep_customer_identity(client, db):
    now, lead = await seed_trial_lead(db)
    await generate_daily_followups(db, now=now)

    resp = await client.post(f"/leads/{lead.id}/transition", json={"to_stage": "lost", "reason": "预算不合"})
    assert resp.status_code == 200

    cancelled = (await client.get("/followups", params={"status": "cancelled"})).json()
    assert cancelled[0]["customer_name"] == "试听家长"
    assert cancelled[0]["lead_stage"] == "lost"


async def test_done_rejected_for_cancelled_followup(client, db):
    now, lead = await seed_trial_lead(db)
    created = await generate_daily_followups(db, now=now)
    assert len(created) == 1

    resp = await client.post(f"/leads/{lead.id}/transition", json={"to_stage": "lost", "reason": "预算不合"})
    assert resp.status_code == 200

    resp = await client.patch(f"/followups/{created[0].id}/done")
    assert resp.status_code == 409
    assert "only pending" in resp.json()["detail"]

    cancelled = (await client.get("/followups", params={"status": "cancelled"})).json()
    assert len(cancelled) == 1
    assert cancelled[0]["status"] == "cancelled"
    assert cancelled[0]["done_at"] is not None
    assert (await client.get("/followups", params={"status": "done"})).json() == []


async def test_done_rejected_twice_keeps_original_done_at(client, db):
    now, lead = await seed_trial_lead(db)
    created = await generate_daily_followups(db, now=now)
    followup_id = created[0].id

    first = await client.patch(f"/followups/{followup_id}/done")
    assert first.status_code == 200
    done_at = first.json()["done_at"]

    again = await client.patch(f"/followups/{followup_id}/done")
    assert again.status_code == 409

    done = (await client.get("/followups", params={"status": "done"})).json()
    assert len(done) == 1
    assert done[0]["done_at"] == done_at


async def test_message_uses_first_student_by_id(client, db):
    now = utcnow()
    customer = Customer(name="多孩家长")
    db.add(customer)
    await db.flush()
    db.add_all([
        CustomerStudent(customer_id=customer.id, subject="数学"),
        CustomerStudent(customer_id=customer.id, subject="英语"),
    ])
    lead = Lead(customer_id=customer.id, stage="new", intent="mid", last_contact_at=now)
    db.add(lead)
    await db.commit()

    created = await generate_daily_followups(db, now=now)
    assert [f.lead_id for f in created] == [lead.id]
    assert "数学辅导" in created[0].suggested_message
    assert "英语" not in created[0].suggested_message
