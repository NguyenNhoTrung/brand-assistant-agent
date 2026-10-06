from shared import redis_keys as keys

BODY = {"conversation_id": None, "input": {"text": "Giá serum?", "mode": "qa"}}


def test_health(client, member, admin):
    assert client.get("/healthz").json() == {"ok": True}
    assert client.get("/readyz").status_code == 200


def test_auth_required_and_invalid(client, member, admin):
    r = client.get("/auth/me")
    assert r.status_code == 401 and r.json()["code"] == "auth_required"
    assert "Basic" in r.headers["WWW-Authenticate"]
    assert (
        client.get("/auth/me", headers={"Authorization": "Basic bUB4LnRlc3Q6d3Jvbmc="}).json()["code"] == "auth_invalid"
    )
    assert client.get("/auth/me", headers=member).json()["role"] == "member"


async def test_create_job_idempotent(client, redis, member, admin):
    h = {**member, "Idempotency-Key": "msg-0001"}
    r1 = client.post("/v1/jobs", json=BODY, headers=h)
    r2 = client.post("/v1/jobs", json=BODY, headers=h)
    assert r1.status_code == 202 and r2.status_code == 200
    assert r1.json()["job_id"] == r2.json()["job_id"]
    assert await redis.llen(keys.QUEUE) == 1


def test_job_of_other_user_is_404(client, member, admin):
    jid = client.post("/v1/jobs", json=BODY, headers={**member, "Idempotency-Key": "msg-0002"}).json()["job_id"]
    assert client.get(f"/v1/jobs/{jid}", headers=member).status_code == 200
    r = client.get(f"/v1/jobs/{jid}", headers=admin)
    assert r.status_code == 404 and r.json()["code"] == "job_not_found"


def test_validation_error_is_problem_json(client, member, admin):
    r = client.post("/v1/jobs", json={"input": {"text": ""}}, headers={**member, "Idempotency-Key": "msg-0003"})
    assert r.status_code == 422 and r.headers["content-type"].startswith("application/problem+json")


async def test_sse_replays_events_until_terminal(client, redis, member, admin):
    jid = client.post("/v1/jobs", json=BODY, headers={**member, "Idempotency-Key": "msg-0004"}).json()["job_id"]
    await redis.xadd(keys.job_events(jid), {"type": "token", "data": '{"delta":"Hi"}'})
    await redis.xadd(keys.job_events(jid), {"type": "message.completed", "data": "{}"})
    with client.stream("GET", f"/v1/jobs/{jid}/events", headers=member) as r:
        body = "".join(r.iter_text())
    assert "event: token" in body and "event: message.completed" in body
