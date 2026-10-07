"""Bước 6: conversation, message, feedback, sources, admin, SSE nâng cao, auth/role."""

import json

import pytest

from gateway.core.auth import UserStore
from gateway.settings import settings
from shared import kb
from shared import redis_keys as keys
from shared.ids import now_ms

BODY = {"conversation_id": None, "input": {"text": "Giá serum?", "mode": "qa"}}
CHUNK = "products/vitamin-c-serum.md#0"
FINAL = {
    "status": "answered",
    "answer_md": "Giá $42 [1]",
    "citations": [{"n": 1, "sid": "S1", "chunk_id": CHUNK, "title": "Vitamin C Serum"}],
    "artifact": None,
    "artifact_md": None,
    "confidence": "high",
    "missing_info": [],
    "compliance": {"passed": True, "warnings": []},
}


def _create(client, headers, key: str, conversation_id: str | None = None) -> dict:
    body = {**BODY, "conversation_id": conversation_id}
    r = client.post("/v1/jobs", json=body, headers={**headers, "Idempotency-Key": key})
    assert r.status_code == 202, r.text
    return r.json()


async def _complete(redis, job: dict, user_id: str = "u_m", ai_id: str | None = None) -> str:
    """Mô phỏng worker `store.save_turn` + publisher (không import ai_service — 2 service độc lập)."""
    jid, cid = job["job_id"], job["conversation_id"]
    n = await redis.llen(keys.conv_msgs(cid))
    user_mid = f"00000000-0000-7000-8000-{n:012d}"
    ai_id = ai_id or f"00000000-0000-7000-8000-{n + 1:012d}"
    owner = {"job_id": jid, "user_id": user_id, "conversation_id": cid, "created_at": now_ms()}
    await redis.set(keys.msg(user_mid), json.dumps({"id": user_mid, "role": "user", "content_md": "Giá?", **owner}))
    ai = {"id": ai_id, "role": "assistant", "content_md": FINAL["answer_md"], **owner, **FINAL}
    del ai["answer_md"]
    await redis.set(keys.msg(ai_id), json.dumps(ai), ex=keys.TTL_30D)
    await redis.rpush(keys.conv_msgs(cid), user_mid, ai_id)
    await redis.set(keys.job_msg(jid), ai_id)
    await redis.hset(keys.conv(cid), mapping={"active_job_id": ""})
    await redis.hset(keys.job(jid), mapping={"status": "succeeded", "finished_at": now_ms()})
    return ai_id


async def _xadd(redis, jid: str, type_: str, data: dict) -> str:
    env = {"v": 1, "job_id": jid, "ts": "2026-10-07T00:00:00Z", "data": data}
    return (await redis.xadd(keys.job_events(jid), {"type": type_, "data": json.dumps(env)})).decode()


def _sse(client, url: str, headers: dict) -> list[tuple[str, dict]]:
    with client.stream("GET", url, headers=headers) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())
    out, event = [], None
    for line in body.splitlines():
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
        elif line.startswith("data:") and event:
            out.append((event, json.loads(line.split(":", 1)[1])))
            event = None
    return out


# ── auth / role ──────────────────────────────────────────────────────────────


def test_member_cannot_call_admin(client, member, admin):
    r = client.get("/admin/kb", headers=member)
    assert r.status_code == 403 and r.json()["code"] == "forbidden"
    assert client.get("/admin/kb", headers=admin).status_code == 200
    assert client.get("/admin/kb").status_code == 401


def test_user_store_skips_missing_password_and_fails_when_none(tmp_path, monkeypatch):
    f = tmp_path / "users.yaml"
    f.write_text(
        "users:\n"
        "  - {id: a, email: a@x.test, role: admin, password_env: T_PW_A}\n"
        "  - {id: b, email: b@x.test, role: member, password_env: T_PW_B}\n"
    )
    monkeypatch.delenv("T_PW_A", raising=False)
    monkeypatch.delenv("T_PW_B", raising=False)
    with pytest.raises(RuntimeError, match="T_PW_A, T_PW_B"):
        UserStore.from_file(str(f))
    monkeypatch.setenv("T_PW_B", "secret-b")
    store = UserStore.from_file(str(f))
    assert store.verify("b@x.test", "secret-b") is not None and store.verify("a@x.test", "") is None


def test_request_id_header_and_problem_body(client, member):
    r = client.get("/v1/jobs/00000000-0000-7000-8000-000000000000", headers=member)
    assert r.status_code == 404
    assert r.headers["x-request-id"].startswith("req_") and r.json()["request_id"] == r.headers["x-request-id"]
    r = client.get("/auth/me", headers={**member, "X-Request-ID": "trace-from-proxy-123"})
    assert r.headers["x-request-id"] == "trace-from-proxy-123"


# ── conversations / messages ─────────────────────────────────────────────────


async def test_conversations_sorted_by_updated_at(client, redis, member, admin):
    first = _create(client, member, "conv-0001")
    second = _create(client, member, "conv-0002")
    _create(client, admin, "conv-0003")  # của user khác → không thấy
    await redis.zadd(keys.user_convs("u_m"), {first["conversation_id"]: now_ms() + 10_000})  # vừa có lượt mới
    ids = [c["id"] for c in client.get("/v1/conversations", headers=member).json()]
    assert ids == [first["conversation_id"], second["conversation_id"]]


async def test_messages_and_active_job(client, redis, member):
    job = _create(client, member, "msg-0001")
    cid = job["conversation_id"]
    active = client.get(f"/v1/conversations/{cid}/active-job", headers=member).json()
    assert active["job_id"] == job["job_id"] and active["status"] == "queued"

    await _complete(redis, job)
    assert client.get(f"/v1/conversations/{cid}/active-job", headers=member).json() is None
    msgs = client.get(f"/v1/conversations/{cid}/messages", headers=member).json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["citations"][0]["chunk_id"] == CHUNK and msgs[1]["confidence"] == "high"


async def test_conversation_and_message_of_other_user_is_404(client, redis, member, admin):
    job = _create(client, member, "own-0001")
    ai_id = await _complete(redis, job)
    cid = job["conversation_id"]
    for url in (f"/v1/conversations/{cid}/messages", f"/v1/conversations/{cid}/active-job"):
        r = client.get(url, headers=admin)
        assert r.status_code == 404 and r.json()["code"] == "conversation_not_found"
    r = client.post(f"/v1/messages/{ai_id}/feedback", json={"rating": 1}, headers=admin)
    assert r.status_code == 404 and r.json()["code"] == "message_not_found"
    r = client.post("/v1/jobs", json={**BODY, "conversation_id": cid}, headers={**admin, "Idempotency-Key": "x-000001"})
    assert r.status_code == 404 and r.json()["code"] == "conversation_not_found"


# ── feedback ─────────────────────────────────────────────────────────────────


async def test_feedback_is_written_to_message(client, redis, member):
    ai_id = await _complete(redis, _create(client, member, "fb-00001"))
    r = client.post(f"/v1/messages/{ai_id}/feedback", json={"rating": -1, "comment": "thiếu giá EU"}, headers=member)
    assert r.status_code == 200 and r.json()["feedback"] == {"rating": -1, "comment": "thiếu giá EU"}
    stored = json.loads(await redis.get(keys.msg(ai_id)))
    assert stored["feedback"]["rating"] == -1 and stored["citations"]  # không mất field khác
    assert await redis.ttl(keys.msg(ai_id)) > 0  # giữ TTL 30 ngày
    assert client.post(f"/v1/messages/{ai_id}/feedback", json={"rating": 5}, headers=member).status_code == 422


async def test_feedback_on_user_message_is_rejected(client, redis, member):
    job = _create(client, member, "fb-00002")
    await _complete(redis, job)
    user_mid = (await redis.lrange(keys.conv_msgs(job["conversation_id"]), 0, 0))[0].decode()
    assert client.post(f"/v1/messages/{user_mid}/feedback", json={"rating": 1}, headers=member).status_code == 422


# ── jobs ─────────────────────────────────────────────────────────────────────


async def test_get_job_includes_result_when_succeeded(client, redis, member):
    job = _create(client, member, "res-0001")
    assert client.get(f"/v1/jobs/{job['job_id']}", headers=member).json()["result"] is None
    await _complete(redis, job)
    view = client.get(f"/v1/jobs/{job['job_id']}", headers=member).json()
    assert view["status"] == "succeeded" and view["result"]["answer_md"] == "Giá $42 [1]"


async def test_stale_running_job_becomes_job_timeout(client, redis, member):
    job = _create(client, member, "stale-001")
    old = now_ms() - (settings.job_timeout_s + 60) * 1000
    await redis.hset(keys.job(job["job_id"]), mapping={"status": "running", "started_at": old})
    view = client.get(f"/v1/jobs/{job['job_id']}", headers=member).json()
    assert view["status"] == "failed" and view["error"]["code"] == "job_timeout"
    assert await redis.hget(keys.conv(job["conversation_id"]), "active_job_id") == b""


# ── SSE ──────────────────────────────────────────────────────────────────────


async def test_sse_resumes_after_last_event_id(client, redis, member):
    jid = _create(client, member, "sse-0001")["job_id"]
    await _xadd(redis, jid, "job.started", {})
    mid = await _xadd(redis, jid, "token", {"delta": "Giá "})
    await _xadd(redis, jid, "token", {"delta": "$42"})
    await _xadd(redis, jid, "message.completed", FINAL)
    events = _sse(client, f"/v1/jobs/{jid}/events", {**member, "Last-Event-ID": mid})
    assert [(t, d["data"].get("delta")) for t, d in events] == [("token", "$42"), ("message.completed", None)]
    r = client.get(f"/v1/jobs/{jid}/events", headers={**member, "Last-Event-ID": "abc"})
    assert r.status_code == 422


async def test_sse_stale_job_ends_with_job_timeout(client, redis, member, monkeypatch):
    monkeypatch.setattr(settings, "sse_block_ms", 10)
    jid = _create(client, member, "sse-0002")["job_id"]
    await _xadd(redis, jid, "job.started", {})
    old = now_ms() - (settings.job_timeout_s + 60) * 1000
    await redis.hset(keys.job(jid), mapping={"status": "running", "started_at": old})
    events = _sse(client, f"/v1/jobs/{jid}/events", member)
    assert events[0][0] == "job.started"
    assert events[-1][0] == "job.failed" and events[-1][1]["data"]["code"] == "job_timeout"


async def test_sse_expired_stream_rebuilds_message_completed(client, redis, member):
    job = _create(client, member, "sse-0003")
    await _complete(redis, job)  # job succeeded, stream job:{id}:events không còn (đã EXPIRE)
    events = _sse(client, f"/v1/jobs/{job['job_id']}/events", member)
    assert len(events) == 1
    t, env = events[0]
    assert t == "message.completed" and env["job_id"] == job["job_id"] and env["v"] == 1
    assert env["data"]["answer_md"] == "Giá $42 [1]" and env["data"]["citations"][0]["n"] == 1


async def test_sse_expired_stream_of_failed_job(client, redis, member):
    jid = _create(client, member, "sse-0004")["job_id"]
    err = {"code": "llm_unavailable", "message": "x"}
    await redis.hset(keys.job(jid), mapping={"status": "failed", "error": json.dumps(err)})
    [(t, env)] = _sse(client, f"/v1/jobs/{jid}/events", member)
    assert t == "job.failed" and env["data"] == err


async def test_cancel_sets_flag_only_for_running_job(client, redis, member):
    job = _create(client, member, "cancel-01")
    assert client.post(f"/v1/jobs/{job['job_id']}/cancel", headers=member).status_code == 202
    assert await redis.exists(keys.job_cancel(job["job_id"]))
    done = _create(client, member, "cancel-02")
    await _complete(redis, done)
    client.post(f"/v1/jobs/{done['job_id']}/cancel", headers=member)
    assert not await redis.exists(keys.job_cancel(done["job_id"]))


# ── sources / health ─────────────────────────────────────────────────────────


def test_source_by_chunk_id(client, qdrant, member):
    qdrant.points[kb.point_id(CHUNK)] = {
        "chunk_id": CHUNK,
        "source_path": "products/vitamin-c-serum.md",
        "title": "Vitamin C Serum",
        "doc_type": "product",
        "section": "Pricing",
        "content": "Price: $42",
        "effective_date": "2026-01-01",
        "version": 2,
        "status": "active",
    }
    r = client.get("/v1/sources/products/vitamin-c-serum.md%230", headers=member)
    assert r.status_code == 200 and r.json()["content"] == "Price: $42" and r.json()["version"] == 2
    r = client.get("/v1/sources/products/missing.md%230", headers=member)
    assert r.status_code == 404 and r.json()["code"] == "source_not_found"
    assert client.get("/v1/sources/products/vitamin-c-serum.md%230").status_code == 401


def test_readyz_checks_qdrant(client, qdrant):
    assert client.get("/readyz").status_code == 200
    qdrant.down = True
    r = client.get("/readyz")
    assert r.status_code == 503 and "qdrant" in r.json()["detail"]


# ── admin ────────────────────────────────────────────────────────────────────


async def test_admin_ingest_enqueues_job_without_conversation(client, redis, admin):
    r = client.post("/admin/ingest", json={"recreate": True}, headers=admin)
    assert r.status_code == 202 and r.json()["conversation_id"] is None
    jid = r.json()["job_id"]
    assert (await redis.lrange(keys.QUEUE, 0, -1)) == [jid.encode()]
    job = await redis.hgetall(keys.job(jid))
    assert job[b"type"] == b"ingest" and json.loads(job[b"input"])["recreate"] is True
    assert client.get("/v1/conversations", headers=admin).json() == []
    view = client.get(f"/v1/jobs/{jid}", headers=admin).json()
    assert view["type"] == "ingest" and view["conversation_id"] is None


async def test_admin_kb_and_traces(client, redis, admin):
    entry = {
        "content_hash": "h",
        "chunk_count": 3,
        "status": "superseded",
        "title": "Old",
        "doc_type": "product",
        "version": 1,
        "effective_date": "2025-01-01",
        "ingested_at": "2026-10-07T00:00:00+00:00",
    }
    await redis.hset(keys.KB_MANIFEST, mapping={"z.md": json.dumps(entry), "a.md": json.dumps(entry)})
    kb_list = client.get("/admin/kb", headers=admin).json()
    assert [e["source_path"] for e in kb_list] == ["a.md", "z.md"] and kb_list[0]["status"] == "superseded"

    assert client.get("/admin/traces", headers=admin).json() == []
    await redis.set(keys.trace("j1"), json.dumps({"user_id": "u_m", "scores": {"status": "answered"}, "spans": []}))
    await redis.zadd(keys.TRACES_RECENT, {"j1": 1, "j-expired": 2})
    rows = client.get("/admin/traces", headers=admin).json()
    assert [r["job_id"] for r in rows] == ["j1"] and rows[0]["scores"] == {"status": "answered"}
    job_id = "00000000-0000-7000-8000-000000000001"
    assert client.get(f"/admin/jobs/{job_id}/trace", headers=admin).status_code == 404
