from tests.test_parser import FULL

SECOND = "预算可以到180，孩子周末都有空，想快点开始。"


async def create_customer(client, name="王女士", source="朋友介绍"):
    resp = await client.post("/customers", json={"name": name, "source": source})
    assert resp.status_code == 201
    return resp.json()


async def test_conversation_creates_lead_with_auto_transition(client):
    customer = await create_customer(client)
    resp = await client.post(
        f"/customers/{customer['id']}/conversations",
        json={"direction": "in", "content": FULL},
    )
    assert resp.status_code == 201
    data = resp.json()

    assert data["lead"]["stage"] == "contacted"
    assert data["lead"]["budget"] == 150
    assert data["lead"]["intent"] == "high"
    assert data["extraction"]["fields"]["grade"] == "初二"
    assert data["extraction"]["parser"] == "rules"
    assert data["auto_events"][0]["from"] == "new"
    assert data["auto_events"][0]["to"] == "contacted"


async def test_budget_evolution_across_conversations(client):
    customer = await create_customer(client)
    await client.post(
        f"/customers/{customer['id']}/conversations",
        json={"direction": "in", "content": FULL},
    )
    resp = await client.post(
        f"/customers/{customer['id']}/conversations",
        json={"direction": "in", "content": SECOND},
    )
    data = resp.json()
    assert data["lead"]["budget"] == 180
    assert data["auto_events"] == []

    conversations = (await client.get(f"/customers/{customer['id']}/conversations")).json()
    assert [c["extracted"].get("budget") for c in conversations] == [150, 180]


async def test_customer_profile_aggregation(client):
    customer = await create_customer(client)
    await client.post(
        f"/customers/{customer['id']}/conversations",
        json={"direction": "in", "content": FULL},
    )
    await client.post(
        f"/customers/{customer['id']}/conversations",
        json={"direction": "in", "content": SECOND},
    )

    resp = await client.get(f"/customers/{customer['id']}/profile")
    assert resp.status_code == 200
    profile = resp.json()
    assert profile["lead_stage"] == "contacted"
    assert len(profile["budget_history"]) == 2
    assert profile["price_sensitivity"] == "low"
    assert "成绩提升" in profile["needs"]
    assert profile["conversation_count"] == 2
    assert profile["decision_speed_days"] is None


async def test_outbound_message_does_not_touch_last_contact(client):
    customer = await create_customer(client)
    await client.post(
        f"/customers/{customer['id']}/conversations",
        json={"direction": "out", "content": "您好，我是李老师。"},
    )
    lead = (await client.get("/leads")).json()[0]
    assert lead["stage"] == "new"
    assert lead["last_contact_at"] is None


async def test_customer_crud_and_filter(client):
    a = await create_customer(client, name="A家长")
    await create_customer(client, name="B家长")
    await client.post(
        f"/customers/{a['id']}/conversations",
        json={"direction": "in", "content": FULL},
    )

    contacted = (await client.get("/customers", params={"stage": "contacted"})).json()
    assert [c["name"] for c in contacted] == ["A家长"]

    resp = await client.patch(f"/customers/{a['id']}", json={"phone": "13800000000"})
    assert resp.json()["phone"] == "13800000000"

    missing = await client.get("/customers/999")
    assert missing.status_code == 404
