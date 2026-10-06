import fakeredis
import pytest

from shared import redis_keys as keys
from shared.contracts.export import build
from shared.ids import uuid7
from shared.lua import Scripts


def test_uuid7_version_and_order():
    a, b = uuid7(), uuid7()
    assert a.version == 7 and b.version == 7
    assert a.int >> 80 <= b.int >> 80


async def test_create_job_is_idempotent():
    r = fakeredis.FakeAsyncRedis()
    s = Scripts(r)
    args = dict(
        user_id="u1",
        conversation_id="c1",
        idem_key="k-123456",
        input_json="{}",
        now_ms=1,
        job_type="chat",
        title="t",
    )
    created1, jid1 = await s.create_job(job_id="j1", **args)
    created2, jid2 = await s.create_job(job_id="j2", **args)
    assert (created1, jid1) == (True, "j1")
    assert (created2, jid2) == (False, "j1")
    assert await r.llen(keys.QUEUE) == 1


@pytest.mark.parametrize("name", ["JobCreate", "FinalPayload", "EventType"])
def test_schema_export_contains(name):
    assert name in build()["$defs"]
