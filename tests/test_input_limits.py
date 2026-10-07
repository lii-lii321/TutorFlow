"""Free-text inputs must respect DB column widths (String limits)."""

NOTE_512 = "n" * 512
NOTE_513 = "n" * 513
TEXT_256 = "x" * 256
TEXT_257 = "x" * 257


async def create_customer(client, **overrides):
    payload = {"name": "王女士"}
    payload.update(overrides)
    return await client.post("/customers", json=payload)


async def create_lead(client):
    created = await create_customer(client)
    customer_id = created.json()["id"]
    await client.post(
        f"/customers/{customer_id}/conversations",
        json={"direction": "in", "content": "孩子初三，想学数学。"},
    )
    lead = (await client.get("/leads")).json()[0]
    return lead["id"]


async def test_customer_text_fields_capped(client):
    assert (await create_customer(client, phone="1" * 33)).status_code == 422
    assert (await create_customer(client, source="s" * 33)).status_code == 422
    assert (await create_customer(client, note=NOTE_513)).status_code == 422

    ok = await create_customer(client, phone="13800000000", source="抖音", note=NOTE_512)
    assert ok.status_code == 201

    customer_id = ok.json()["id"]
    assert (await client.patch(f"/customers/{customer_id}", json={"note": NOTE_513})).status_code == 422
    assert (await client.patch(f"/customers/{customer_id}", json={"note": NOTE_512})).status_code == 200


async def test_student_text_fields_capped(client):
    created = await create_customer(client)
    url = f"/customers/{created.json()['id']}/students"

    assert (await client.post(url, json={"name": "n" * 65})).status_code == 422
    assert (await client.post(url, json={"grade": "g" * 33})).status_code == 422
    assert (await client.post(url, json={"subject": "s" * 33})).status_code == 422

    ok = await client.post(url, json={"name": "n" * 64, "grade": "g" * 32, "subject": "数学"})
    assert ok.status_code == 201


async def test_lead_update_text_fields_capped(client):
    lead_id = await create_lead(client)

    assert (await client.patch(f"/leads/{lead_id}", json={"next_action": TEXT_257})).status_code == 422
    ok = await client.patch(f"/leads/{lead_id}", json={"next_action": TEXT_256})
    assert ok.status_code == 200
    assert ok.json()["next_action"] == TEXT_256
    assert (await client.patch(f"/leads/{lead_id}", json={"closed_reason": TEXT_257})).status_code == 422


async def test_transition_reason_capped(client):
    lead_id = await create_lead(client)

    bad = await client.post(f"/leads/{lead_id}/transition", json={"to_stage": "qualified", "reason": TEXT_257})
    assert bad.status_code == 422

    ok = await client.post(f"/leads/{lead_id}/transition", json={"to_stage": "qualified", "reason": TEXT_256})
    assert ok.status_code == 200
    assert ok.json()["stage"] == "qualified"
