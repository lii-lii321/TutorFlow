from tests.test_parser import FULL


async def seed_won_lead(client):
    customer = (await client.post("/customers", json={"name": "王女士", "source": "朋友介绍"})).json()
    await client.post(
        f"/customers/{customer['id']}/conversations",
        json={"direction": "in", "content": FULL},
    )
    lead = (await client.get("/leads")).json()[0]
    for stage in ("qualified", "trial", "won"):
        resp = await client.post(
            f"/leads/{lead['id']}/transition", json={"to_stage": stage, "reason": "test"}
        )
        assert resp.status_code == 200
    return lead


async def test_handoff_produces_teacheros_payload(client):
    lead = await seed_won_lead(client)

    resp = await client.post(f"/leads/{lead['id']}/handoff")
    assert resp.status_code == 200
    body = resp.json()
    payload = body["teacheros_student"]
    assert payload["name"] == "王女士的孩子"
    assert payload["grade"] == "初二"
    assert payload["subject"] == "数学"
    assert payload["current_score"] == 80
    assert payload["target_score"] == 100
    assert "朋友介绍" in payload["teacher_note"]
    assert "150" in payload["teacher_note"]


async def test_handoff_is_idempotent_guarded(client):
    lead = await seed_won_lead(client)
    first = await client.post(f"/leads/{lead['id']}/handoff")
    assert first.status_code == 200
    second = await client.post(f"/leads/{lead['id']}/handoff")
    assert second.status_code == 409
    assert "already" in second.json()["detail"]


async def test_handoff_rejects_non_won_lead(client):
    customer = (await client.post("/customers", json={"name": "李女士"})).json()
    await client.post(
        f"/customers/{customer['id']}/conversations",
        json={"direction": "in", "content": FULL},
    )
    lead = (await client.get("/leads")).json()[0]
    resp = await client.post(f"/leads/{lead['id']}/handoff")
    assert resp.status_code == 409
    assert "won" in resp.json()["detail"]


async def test_handoff_missing_lead_404(client):
    resp = await client.post("/leads/999/handoff")
    assert resp.status_code == 404
