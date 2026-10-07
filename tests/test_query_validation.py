"""Enum-like query params must reject bogus values with 422, not return silent empty lists."""


async def test_leads_reject_bogus_stage_and_intent(client):
    assert (await client.get("/leads", params={"stage": "archived"})).status_code == 422
    assert (await client.get("/leads", params={"intent": "hot"})).status_code == 422

    assert (await client.get("/leads", params={"stage": "trial"})).status_code == 200
    assert (await client.get("/leads", params={"intent": "low"})).status_code == 200


async def test_customers_reject_bogus_stage(client):
    assert (await client.get("/customers", params={"stage": "deleted"})).status_code == 422
    assert (await client.get("/customers", params={"stage": "won"})).status_code == 200


async def test_followups_reject_bogus_status(client):
    assert (await client.get("/followups", params={"status": "archived"})).status_code == 422

    for allowed in ("pending", "done", "cancelled", "all"):
        resp = await client.get("/followups", params={"status": allowed})
        assert resp.status_code == 200
