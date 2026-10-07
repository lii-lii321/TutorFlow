async def test_healthz(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_root(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert resp.json()["app"] == "TutorFlow"


async def test_lead_transition_endpoint(client):
    created = await client.post("/customers", json={"name": "测试家长"})
    customer = created.json()
    await client.post(
        f"/customers/{customer['id']}/conversations",
        json={"direction": "in", "content": "孩子初三，想学数学，什么时候可以试听？"},
    )
    lead = (await client.get("/leads")).json()[0]

    ok = await client.post(
        f"/leads/{lead['id']}/transition",
        json={"to_stage": "qualified", "reason": "确认了年级和科目"},
    )
    assert ok.status_code == 200
    assert ok.json()["stage"] == "qualified"

    bad = await client.post(
        f"/leads/{lead['id']}/transition",
        json={"to_stage": "won"},
    )
    assert bad.status_code == 409
    assert "cannot transition" in bad.json()["detail"]

    detail = await client.get(f"/leads/{lead['id']}")
    stages = [event["to_stage"] for event in detail.json()["events"]]
    assert stages == ["contacted", "qualified"]


async def test_lead_filters(client):
    resp = await client.get("/leads", params={"stage": "new", "intent": "mid"})
    assert resp.status_code == 200


async def seed_lead(client, name):
    created = await client.post("/customers", json={"name": name})
    customer_id = created.json()["id"]
    await client.post(
        f"/customers/{customer_id}/conversations",
        json={"direction": "in", "content": "孩子初三，想学数学。"},
    )
    return (await client.get("/leads")).json()[0]["id"]


async def test_leads_read_endpoints_include_customer_name(client):
    lead_id = await seed_lead(client, "管道家长")

    listed = (await client.get("/leads")).json()
    assert listed[0]["customer_name"] == "管道家长"

    detail = (await client.get(f"/leads/{lead_id}")).json()
    assert detail["customer_name"] == "管道家长"


async def test_leads_write_endpoints_include_customer_name(client):
    lead_id = await seed_lead(client, "成交家长")

    patched = await client.patch(f"/leads/{lead_id}", json={"next_action": "发送课程方案"})
    assert patched.json()["customer_name"] == "成交家长"

    transitioned = await client.post(f"/leads/{lead_id}/transition", json={"to_stage": "qualified"})
    assert transitioned.json()["customer_name"] == "成交家长"
