import pytest

from tests.test_parser import FULL

BULK_LOG = (
    "2024-10-01 10:30 王女士: " + FULL + "\n"
    "我：好的，先给孩子做一次学情诊断。\n"
    "王女士：计算还可以，应用题薄弱，想快点开始。\n"
)


async def create_customer(client, name="王女士"):
    resp = await client.post("/customers", json={"name": name, "source": "朋友介绍"})
    return resp.json()


async def test_bulk_ingest_creates_lead_and_profile(client):
    customer = await create_customer(client)
    resp = await client.post(
        f"/customers/{customer['id']}/conversations/bulk",
        json={"text": BULK_LOG},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ingested"] == 3
    assert body["lead_stage"] == "contacted"
    assert body["auto_events_total"] == 1

    conversations = (await client.get(f"/customers/{customer['id']}/conversations")).json()
    assert [c["direction"] for c in conversations] == ["in", "out", "in"]
    assert conversations[0]["extracted"]["budget"] == 150

    profile = (await client.get(f"/customers/{customer['id']}/profile")).json()
    assert profile["lead_stage"] == "contacted"
    assert profile["needs"]


async def test_bulk_ingest_empty_text_422(client):
    customer = await create_customer(client)
    resp = await client.post(
        f"/customers/{customer['id']}/conversations/bulk",
        json={"text": "   \n  "},
    )
    assert resp.status_code == 422


async def test_bulk_ingest_missing_customer_404(client):
    resp = await client.post(
        "/customers/999/conversations/bulk",
        json={"text": "你好"},
    )
    assert resp.status_code == 404


async def test_handoff_then_teacheros_payload_shape(client):
    customer = await create_customer(client)
    await client.post(
        f"/customers/{customer['id']}/conversations/bulk",
        json={"text": BULK_LOG},
    )
    lead = (await client.get("/leads")).json()[0]
    for stage in ("qualified", "trial", "won"):
        await client.post(f"/leads/{lead['id']}/transition", json={"to_stage": stage, "reason": "t"})

    handoff = await client.post(f"/leads/{lead['id']}/handoff")
    payload = handoff.json()["teacheros_student"]
    assert set(payload) == {"name", "grade", "subject", "current_score", "target_score", "teacher_note"}
    assert payload["grade"] == "初二"
    assert payload["current_score"] == 80


async def test_bulk_occurred_at_with_timezone_normalized_to_utc(client):
    customer = await create_customer(client)
    resp = await client.post(
        f"/customers/{customer['id']}/conversations/bulk",
        json={"text": BULK_LOG, "occurred_at": "2026-10-05T18:30:00+08:00"},
    )
    assert resp.status_code == 200

    conversations = (await client.get(f"/customers/{customer['id']}/conversations")).json()
    assert [c["occurred_at"] for c in conversations] == ["2026-10-05T10:30:00"] * 3

    lead = (await client.get("/leads")).json()[0]
    assert lead["last_contact_at"] == "2026-10-05T10:30:00"
