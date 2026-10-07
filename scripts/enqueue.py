"""Đẩy job vào `queue:jobs` (thay gateway khi test worker) rồi in event tới khi kết thúc.

    uv run --env-file .env python scripts/enqueue.py "How much is the Vitamin C Serum?" --mode qa
    uv run --env-file .env python scripts/enqueue.py "thế còn giá của nó?" --conv <conversation_id>
    uv run --env-file .env python scripts/enqueue.py "Creative brief for SPF 50" --mode creative_brief --cancel-after 3
    uv run --env-file .env python scripts/enqueue.py --ingest [--recreate]
    uv run --env-file .env python scripts/enqueue.py "Q" -n 6 --no-wait     # đẩy 6 job (test nhiều worker)

Thoát mã 0 khi `message.completed`, 1 khi `job.failed`/`job.cancelled`/hết thời gian chờ.
"""

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from typing import Any

from redis.asyncio import Redis

from shared import redis_keys as keys
from shared.contracts import TERMINAL_EVENTS
from shared.ids import now_ms, uuid7
from shared.lua import Scripts

DIM, BOLD, RED, GREEN, RESET = "\033[2m", "\033[1m", "\033[31m", "\033[32m", "\033[0m"


async def create(r: Redis, args: argparse.Namespace, conv_id: str) -> str:
    job_id = str(uuid7())
    payload: dict = {"text": args.text or "ingest", "mode": args.mode}
    if args.ingest:
        payload["recreate"] = args.recreate
    created, jid = await Scripts(r).create_job(
        job_id=job_id,
        user_id=args.user,
        conversation_id=conv_id,
        idem_key=uuid.uuid4().hex,
        input_json=json.dumps(payload, ensure_ascii=False),
        now_ms=now_ms(),
        job_type="ingest" if args.ingest else "chat",
        title=(args.text or "ingest")[:60],
    )
    assert created, "idempotency key trùng — không thể xảy ra với uuid4"
    return jid


def show(type_: str, data: dict | list, t0: float) -> None:
    ts = f"{DIM}{time.monotonic() - t0:6.2f}s{RESET}"
    if type_ == "token":
        print(data["delta"], end="", flush=True)  # type: ignore[call-overload]
        return
    if type_ == "message.completed":
        assert isinstance(data, dict)
        print(
            f"\n{ts} {GREEN}{BOLD}message.completed{RESET} status={data['status']} confidence={data.get('confidence')}"
        )
        print(data["answer_md"])
        if data.get("artifact_md"):
            print(f"{BOLD}── artifact ──{RESET}\n{data['artifact_md']}")
        for c in data.get("citations", []):
            print(f"  [{c['n']}] {c['title']} — {c['section'][:60]} ({c['chunk_id']})")
        return
    color = RED if type_ in {"job.failed", "job.cancelled"} else ""
    detail = json.dumps(data, ensure_ascii=False)
    print(f"\n{ts} {color}{type_}{RESET} {DIM}{detail[:160]}{RESET}", end="", flush=True)


async def follow(r: Redis, job_id: str, *, cancel_after: int | None, timeout_s: float) -> str:
    t0, last_id, n = time.monotonic(), "0-0", 0
    while time.monotonic() - t0 < timeout_s:
        resp: Any = await r.xread({keys.job_events(job_id): last_id}, block=2000, count=100)
        for _, entries in resp or []:
            for eid, fields in entries:
                last_id = eid.decode()
                type_ = fields[b"type"].decode()
                show(type_, json.loads(fields[b"data"])["data"], t0)
                n += 1
                if cancel_after is not None and n == cancel_after:
                    await r.set(keys.job_cancel(job_id), 1, ex=keys.TTL_1H)
                    print(f"\n{RED}→ đã đặt cờ hủy sau {n} event{RESET}", end="")
                if type_ in TERMINAL_EVENTS:
                    print()
                    return type_
    print(f"\n{RED}hết {timeout_s:.0f}s chờ mà chưa có event kết thúc{RESET}")
    return "timeout"


async def main(args: argparse.Namespace) -> int:
    r = Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    try:
        conv_id = args.conv or str(uuid7())
        job_ids = [await create(r, args, conv_id if i == 0 else str(uuid7())) for i in range(args.n)]
        for jid in job_ids:
            print(f"{BOLD}job_id={jid}{RESET}")
        print(f"{BOLD}conversation_id={conv_id}{RESET}")
        if args.no_wait:
            return 0
        terminal = await follow(r, job_ids[0], cancel_after=args.cancel_after, timeout_s=args.timeout)
        status: Any = await r.hget(keys.job(job_ids[0]), "status")
        print(f"{DIM}job:{job_ids[0]} status={status.decode() if status else '?'}{RESET}")
        return 0 if terminal == "message.completed" else 1
    finally:
        await r.aclose()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Đẩy job vào worker và theo dõi event")
    p.add_argument("text", nargs="?", help="câu hỏi (bỏ trống khi --ingest)")
    p.add_argument("--mode", default="auto")
    p.add_argument("--conv", help="conversation_id có sẵn — cùng conv = cùng hội thoại (checkpoint)")
    p.add_argument("--user", default="script")
    p.add_argument("--ingest", action="store_true", help="job type=ingest (nạp lại data/knowledge)")
    p.add_argument("--recreate", action="store_true", help="với --ingest: xóa collection rồi nạp lại")
    p.add_argument("--cancel-after", type=int, help="đặt cờ hủy sau N event")
    p.add_argument("-n", type=int, default=1, help="số job đẩy (mỗi job một conversation riêng)")
    p.add_argument("--no-wait", action="store_true", help="chỉ đẩy job, không theo dõi event")
    p.add_argument("--timeout", type=float, default=240)
    a = p.parse_args()
    if not a.ingest and not a.text:
        p.error("cần câu hỏi (hoặc --ingest)")
    sys.exit(asyncio.run(main(a)))
