"""Chạy graph trực tiếp (không worker/gateway) — công cụ debug chính của Bước 4.

    python -m ai_service.cli "How much is the Vitamin C Serum?" --mode qa
    python -m ai_service.cli "Tell me about the Vitamin C Serum" --thread t9
    python -m ai_service.cli "thế còn giá của nó?" --thread t9     # lượt 2 cùng thread → nhớ ngữ cảnh

Checkpoint mặc định lưu Redis (AsyncRedisSaver) để nhiều lần gọi CLI cùng `--thread` nối được hội thoại;
`--memory` dùng InMemorySaver (chỉ sống trong một lần chạy). Redis + Qdrant vẫn cần cho retrieval.
"""

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from contextlib import AsyncExitStack
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from redis.asyncio import Redis

from ai_service.agent.context import RunContext
from ai_service.agent.graph import STREAMABLE_NODES, build_graph
from ai_service.llm.client import embeddings
from ai_service.rag.qdrant_store import make_client
from ai_service.rag.retriever import Retriever
from ai_service.settings import settings
from shared.contracts.jobs import Mode

DIM, BOLD, RESET = "\033[2m", "\033[1m", "\033[0m"


def _print_event(kind: str, data: Any) -> None:
    if kind == "node.started":
        print(f"{DIM}▸ {data['node']}: {data['label']}{RESET}", file=sys.stderr)
    elif kind == "route.decided":
        print(f"{DIM}  intent={data['intent']} doc_types={data['doc_types']}{RESET}", file=sys.stderr)
    elif kind == "retrieval.sources":
        for s in data:
            print(f"{DIM}  {s['sid']:<4} {s['chunk_id']:<45} {s['section'][:50]}{RESET}", file=sys.stderr)
    elif kind == "verification.result":
        mark = "✓ pass" if data["passed"] else f"✗ {len(data['issues'])} issue(s)"
        print(f"{DIM}  verify (revision {data['revision']}): {mark}{RESET}", file=sys.stderr)
        for i in data["issues"]:
            print(
                f"{DIM}    - {i['kind']} {i.get('rule_id') or ''} [{i['severity']}] {i['excerpt'][:90]!r}{RESET}",
                file=sys.stderr,
            )
    elif kind == "answer.revised":
        print(f"\n{DIM}  … đang viết lại bản nháp (revision {data['revision']}){RESET}", file=sys.stderr)


async def run(question: str, mode: str, thread: str, *, memory: bool, raw: bool, quiet: bool) -> dict:
    async with AsyncExitStack() as stack:
        redis = Redis.from_url(settings.redis_url)
        stack.push_async_callback(redis.aclose)
        qdrant = make_client()
        stack.push_async_callback(qdrant.close)
        saver: BaseCheckpointSaver
        if memory:
            saver = InMemorySaver()
        else:
            redis_saver = await stack.enter_async_context(AsyncRedisSaver.from_conn_string(settings.redis_url))
            await redis_saver.asetup()
            saver = redis_saver
        graph = build_graph(saver, retriever=Retriever(qdrant, embeddings(redis), settings.qdrant_collection))

        config: RunnableConfig = {"configurable": {"thread_id": f"cli:{thread}"}}
        ctx = RunContext(job_id=str(uuid.uuid4()), user_id="cli", mode=mode)
        t0 = time.perf_counter()
        part: Any
        async for part in graph.astream(
            {"messages": [HumanMessage(question)], "requested_mode": mode},
            config,
            context=ctx,
            stream_mode=["custom", "messages"],
        ):
            kind, chunk = part
            if quiet:
                continue
            if kind == "custom":
                _print_event(chunk["type"], chunk["data"])
            elif kind == "messages":
                msg, meta = chunk
                if meta.get("langgraph_node") in STREAMABLE_NODES and isinstance(msg.content, str):
                    print(f"{DIM}{msg.content}{RESET}", end="", file=sys.stderr, flush=True)
        final: dict = (await graph.aget_state(config)).values["final"]

    if raw:
        print(json.dumps(final, ensure_ascii=False, indent=2))
        return final
    print(f"\n\n{BOLD}── FinalPayload ({time.perf_counter() - t0:.1f}s) ──{RESET}")
    print(
        f"status={final['status']}  confidence={final['confidence']}  compliance.passed={final['compliance']['passed']}"
    )
    print(f"\n{final['answer_md']}\n")
    if final.get("artifact_md"):
        print(f"{BOLD}── artifact ──{RESET}\n{final['artifact_md']}")
    for c in final["citations"]:
        print(f"[{c['n']}] {c['title']} — {c['section'][:60]} ({c['chunk_id']})")
    if final["missing_info"]:
        print(f"missing_info: {final['missing_info']}")
    for w in final["compliance"]["warnings"]:
        print(f"⚠ {w['kind']} {w.get('rule_id') or ''} [{w['severity']}] {w['excerpt'][:100]!r}")
    return final


def main() -> None:
    p = argparse.ArgumentParser(description="Chạy agent graph trực tiếp")
    p.add_argument("question")
    p.add_argument("--mode", default="auto", choices=list(Mode.__args__))  # type: ignore[attr-defined]
    p.add_argument("--thread", default=None, help="thread_id — cùng thread = cùng hội thoại (mặc định: mới)")
    p.add_argument("--memory", action="store_true", help="InMemorySaver thay vì Redis (không nhớ giữa các lần chạy)")
    p.add_argument("--redis", action="store_true", help="(mặc định) checkpoint AsyncRedisSaver")
    p.add_argument("--json", action="store_true", help="chỉ in FinalPayload dạng JSON")
    args = p.parse_args()
    settings.require_openai_key()
    thread = args.thread or uuid.uuid4().hex[:8]
    asyncio.run(run(args.question, args.mode, thread, memory=args.memory, raw=args.json, quiet=args.json))
    # onnxruntime (FastEmbed BM25) đôi khi abort lúc huỷ thread pool khi interpreter tắt trên macOS
    # ("recursive_mutex lock failed") → thoát thẳng sau khi flush để `ask … && ask …` không bị đứt.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
