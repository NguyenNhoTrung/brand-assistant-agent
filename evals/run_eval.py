"""Eval độ chính xác của ai-service: chạy golden set thẳng vào agent graph (không worker/gateway) (§19).

    uv run --env-file .env python -m evals.run_eval                      # toàn bộ golden set
    uv run --env-file .env python -m evals.run_eval --only qa-001,cmp-   # lọc theo id / tiền tố
    uv run --env-file .env python -m evals.run_eval --no-judge           # chỉ metric deterministic, rẻ hơn

Cần: Redis + Qdrant đang chạy, KB đã ingest (`make ingest-local`), OPENAI_API_KEY thật.
Ghi `<report>.json` (từng case) + `<report>.md` (bảng tổng + diff baseline); exit 1 nếu dưới ngưỡng.
"""

import argparse
import asyncio
import json
import math
import os
import re
import sys
import time
import uuid
from contextlib import AsyncExitStack
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from redis.asyncio import Redis

from ai_service.agent.context import RunContext
from ai_service.agent.graph import Graph, build_graph
from ai_service.compliance.deterministic import field_texts, strip_quoted
from ai_service.llm.client import embeddings
from ai_service.rag.citations import parse_citations
from ai_service.rag.qdrant_store import make_client
from ai_service.rag.retriever import Retriever
from ai_service.settings import settings
from ai_service.skills.registry import get_skill
from evals import judges

EVALS_DIR = Path(__file__).parent
ABSTAIN_STATUSES = {"abstained", "out_of_scope"}
RULE_ID = re.compile(r"\b[A-Z]{3}-\d{3}\b")
TOP_K = 5


# ───────────────────────── chạy graph ─────────────────────────


async def run_case(graph: Graph, case: dict, sem: asyncio.Semaphore) -> dict[str, Any]:
    async with sem:
        usage = UsageMetadataCallbackHandler()
        config: RunnableConfig = {
            "configurable": {"thread_id": f"eval:{case['id']}:{uuid.uuid4().hex[:8]}"},
            "callbacks": [usage],
        }
        ctx = RunContext(job_id=str(uuid.uuid4()), user_id="eval", mode=case["mode"])
        t0 = time.perf_counter()
        try:
            await graph.ainvoke(
                {"messages": [HumanMessage(case["q"])], "requested_mode": case["mode"]}, config, context=ctx
            )
        except Exception as e:  # một case lỗi không làm hỏng cả lượt eval
            return {"case": case, "error": f"{type(e).__name__}: {e}", "latency_s": time.perf_counter() - t0}
        latency = time.perf_counter() - t0
        values = (await graph.aget_state(config)).values
        print(f"  ✓ {case['id']:<8} {values['final']['status']:<13} {latency:5.1f}s", file=sys.stderr)
        return {
            "case": case,
            "final": values["final"],
            "evidence": values.get("evidence") or [],
            "draft_md": values.get("draft_md") or "",
            "intent": (values.get("route") or {}).get("intent"),
            "revision_count": values.get("revision_count", 0),
            "latency_s": latency,
            "usage": {m: dict(u) for m, u in usage.usage_metadata.items()},
        }


# ───────────────────────── chấm từng case ─────────────────────────


def _norm(s: str) -> str:
    s = s.lower().replace("–", "-").replace("—", "-").replace(" ", " ")
    s = re.sub(r"(?<=\d),(?=\d{3})", "", s)  # 1,200 → 1200
    return re.sub(r"\s+", " ", s).strip()


def _contains(text: str, needle: str) -> bool:
    return _norm(needle) in _norm(text)


@cache
def _rubric(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


async def score_case(run: dict[str, Any], *, judge: bool) -> dict[str, Any]:
    case = run["case"]
    res: dict[str, Any] = {
        "id": case["id"],
        "mode": case["mode"],
        "q": case["q"],
        "latency_s": round(run["latency_s"], 2),
        "failures": [],
    }
    if "error" in run:
        res.update(status="error", error=run["error"], passed=False, failures=["error"])
        return res

    final, evidence = run["final"], run["evidence"]
    artifact = final.get("artifact")
    skill = get_skill(run["intent"] or case["mode"]) if artifact else None
    answer = final["answer_md"] + "\n\n" + (final.get("artifact_md") or "")
    sources = [e["source_path"] for e in evidence]
    fails: list[str] = res["failures"]
    res.update(
        status=final["status"],
        kind="artifact" if artifact or get_skill(case["mode"]) else "qa",
        confidence=final.get("confidence"),
        revision_count=run["revision_count"],
        retrieved=sources,
        answer_md=final["answer_md"],
        artifact_md=final.get("artifact_md"),
        usage=run["usage"],
    )

    # Retrieval Recall@5 (+ recall trên toàn bộ evidence để biết trượt do xếp hạng hay do không tìm thấy)
    if exp := case.get("expected_sources"):
        top = set(sources[:TOP_K])
        res["recall_at_5"] = sum(s in top for s in exp) / len(exp)
        res["recall_all"] = sum(s in set(sources) for s in exp) / len(exp)
        res["missed_sources"] = [s for s in exp if s not in top]
        if res["recall_at_5"] < 1:
            fails.append("recall")

    # Citation validity: mọi [S#] trong bản nháp cuối/artifact phải trỏ tới evidence của lượt
    raw = run["draft_md"] + "\n" + (skill.render(artifact) if skill and artifact else "")
    cited = parse_citations(raw)
    valid_sids = {e["sid"] for e in evidence}
    res["citations_total"] = len(cited)
    res["citations_invalid"] = [s for s in cited if s not in valid_sids]
    if res["citations_invalid"]:
        fails.append("citation")

    # Expected facts: khớp chuỗi, trượt thì hỏi judge
    if facts := case.get("expected_facts"):
        found: dict[str, str] = {}
        for f in facts:
            if _contains(answer, f):
                found[f] = "match"
            elif judge:
                fv = await judges.fact_present(answer, f)
                found[f] = "judge" if fv.present else f"missing: {fv.reason}"
            else:
                found[f] = "missing"
        res["facts"] = found
        res["facts_hit"] = sum(v in ("match", "judge") for v in found.values())
        res["facts_total"] = len(facts)
        if res["facts_hit"] < len(facts):
            fails.append("facts")

    # Forbidden facts (bản cũ / injection): có chuỗi chưa chắc là khẳng định → judge quyết
    if forb := case.get("forbidden_facts"):
        asserted: dict[str, str] = {}
        for f in forb:
            if not _contains(answer, f):
                continue
            if judge:
                cv = await judges.claim_asserted(answer, f)
                if cv.asserted:
                    asserted[f] = cv.reason
            else:
                asserted[f] = "chuỗi xuất hiện (không có judge)"
        res["forbidden_asserted"] = asserted
        if asserted:
            fails.append("forbidden_fact")

    # Abstain
    res["should_abstain"] = bool(case.get("should_abstain", False))
    res["abstained"] = final["status"] in ABSTAIN_STATUSES
    if res["should_abstain"] != res["abstained"]:
        fails.append("abstain")

    # Compliance: forbidden_patterns trong field publishable (artifact) hoặc Q&A đã bỏ trích dẫn
    if pats := case.get("forbidden_patterns"):
        if artifact and skill:
            texts = field_texts(artifact, skill.publishable_fields)
        else:
            texts = {"answer_md": strip_quoted(final["answer_md"])}
        hits = [
            {"field": name, "pattern": p, "match": m.group(0)}
            for name, text in texts.items()
            for p in pats
            if (m := re.search(p, text, re.IGNORECASE))
        ]
        res["compliance_hits"] = hits
        if hits:
            fails.append("compliance")

    # Rule refs: rule_id trong warnings / compliance_notes / văn bản
    if refs := case.get("expected_rule_refs"):
        got = {w["rule_id"] for w in final["compliance"]["warnings"] if w.get("rule_id")}
        got |= {n.get("rule_id") for n in (artifact or {}).get("compliance_notes") or []}
        got |= set(RULE_ID.findall(answer))
        res["rule_refs_found"] = [r for r in refs if r in got]
        res["rule_refs_total"] = len(refs)
        if len(res["rule_refs_found"]) < len(refs):
            fails.append("rule_refs")

    # Artifact rubric (LLM judge, 1–5)
    if judge and artifact and skill and final.get("artifact_md"):
        block = "\n\n".join(f"[{e['sid']}] {e['title']} › {e['section']}\n{e['text']}" for e in evidence)
        rubric = _rubric(skill.rubric_path)
        rv = await judges.rubric_scores(rubric, case["q"], final["artifact_md"], block)
        res["rubric"] = {s.id: s.score for s in rv.scores}
        res["rubric_reasons"] = {s.id: s.reason for s in rv.scores}
        res["rubric_avg"] = round(sum(s.score for s in rv.scores) / max(len(rv.scores), 1), 2)
        if res["rubric_avg"] < rubric.get("pass_threshold", 4):
            fails.append("rubric")

    res["passed"] = not fails
    return res


# ───────────────────────── tổng hợp ─────────────────────────


def _mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 4) if xs else None


def _p95(xs: list[float]) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    return round(s[min(len(s) - 1, math.ceil(0.95 * len(s)) - 1)], 2)


def aggregate(results: list[dict]) -> dict[str, Any]:
    ok = [r for r in results if r["status"] != "error"]
    tp = sum(r["should_abstain"] and r["abstained"] for r in ok)
    pred = sum(r["abstained"] for r in ok)
    actual = sum(r["should_abstain"] for r in ok)
    cites = sum(r["citations_total"] for r in ok)
    tokens: dict[str, dict[str, int]] = {}
    for r in ok:
        for model, u in r["usage"].items():
            t = tokens.setdefault(model, {"input_tokens": 0, "output_tokens": 0})
            t["input_tokens"] += u.get("input_tokens", 0)
            t["output_tokens"] += u.get("output_tokens", 0)
    with_forbidden = [r for r in ok if "forbidden_asserted" in r]
    return {
        "cases": len(results),
        "passed": sum(r["passed"] for r in results),
        "errors": len(results) - len(ok),
        "recall_at_5": _mean([r["recall_at_5"] for r in ok if "recall_at_5" in r]),
        "recall_all": _mean([r["recall_all"] for r in ok if "recall_all" in r]),
        "citation_validity": round(1 - sum(len(r["citations_invalid"]) for r in ok) / cites, 4) if cites else None,
        "expected_facts": (
            round(sum(r["facts_hit"] for r in ok if "facts" in r) / n, 4)
            if (n := sum(r["facts_total"] for r in ok if "facts" in r))
            else None
        ),
        "forbidden_facts_rate": _mean([float(bool(r["forbidden_asserted"])) for r in with_forbidden]),
        "abstain_precision": round(tp / pred, 4) if pred else None,
        "abstain_recall": round(tp / actual, 4) if actual else None,
        "compliance_violations": sum(bool(r.get("compliance_hits")) for r in ok),
        "rule_ref_recall": (
            round(sum(len(r["rule_refs_found"]) for r in ok if "rule_refs_total" in r) / n, 4)
            if (n := sum(r["rule_refs_total"] for r in ok if "rule_refs_total" in r))
            else None
        ),
        "artifact_rubric": _mean([r["rubric_avg"] for r in ok if "rubric_avg" in r]),
        "latency_p95_qa_s": _p95([r["latency_s"] for r in ok if r["kind"] == "qa"]),
        "latency_p95_artifact_s": _p95([r["latency_s"] for r in ok if r["kind"] == "artifact"]),
        "tokens": tokens,
    }


def check_thresholds(metrics: dict, thresholds: dict) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for name, t in thresholds.items():
        v = metrics.get(name)
        if v is None:
            continue
        out[name] = ("min" not in t or v >= t["min"]) and ("max" not in t or v <= t["max"])
    return out


# ───────────────────────── report ─────────────────────────


def _fmt(v: Any) -> str:
    return "—" if v is None else f"{v:.3f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def render_md(report: dict, thresholds: dict, baseline: dict | None) -> str:
    m, checks = report["metrics"], report["threshold_checks"]
    bm = (baseline or {}).get("metrics", {})
    lines = [
        f"# Eval ai-service — {report['meta']['started_at']}",
        "",
        f"**{m['passed']}/{m['cases']} case pass** · lỗi: {m['errors']} · judge: {report['meta']['judge']}"
        + (f" · baseline: `{report['meta']['baseline']}`" if baseline else ""),
        "",
        "| Metric | Giá trị | Ngưỡng | Đạt | Baseline | Δ |",
        "|---|---|---|---|---|---|",
    ]
    for name in [k for k in m if k != "tokens"]:
        t = thresholds.get(name, {})
        thr = " ".join(f"{'≥' if k == 'min' else '≤'} {v}" for k, v in t.items()) or ""
        ok = {True: "✅", False: "❌"}.get(checks[name], "") if name in checks else ""
        b = bm.get(name)
        delta = f"{m[name] - b:+.3f}" if isinstance(m[name], int | float) and isinstance(b, int | float) else ""
        lines.append(f"| {name} | {_fmt(m[name])} | {thr} | {ok} | {_fmt(b)} | {delta} |")

    if m["tokens"]:
        lines += ["", "| Model | input tokens | output tokens |", "|---|---|---|"]
        lines += [f"| {k} | {v['input_tokens']} | {v['output_tokens']} |" for k, v in m["tokens"].items()]

    if baseline:
        before = {c["id"]: c["passed"] for c in baseline.get("cases", [])}
        now = {c["id"]: c["passed"] for c in report["cases"]}
        regressed = [i for i, p in now.items() if before.get(i) is True and not p]
        fixed = [i for i, p in now.items() if before.get(i) is False and p]
        lines += ["", "## So với baseline", "", f"- pass → fail: {', '.join(regressed) or 'không có'}"]
        lines.append(f"- fail → pass: {', '.join(fixed) or 'không có'}")

    lines += ["", "## Từng case", "", "| Case | Mode | Status | Latency | Pass | Lỗi |", "|---|---|---|---|---|---|"]
    for c in report["cases"]:
        lines.append(
            f"| {c['id']} | {c['mode']} | {c['status']} | {c['latency_s']}s | {'✅' if c['passed'] else '❌'} "
            f"| {', '.join(c['failures'])} |"
        )

    failed = [c for c in report["cases"] if not c["passed"]]
    if failed:
        lines += ["", "## Chi tiết case fail"]
        for c in failed:
            lines += ["", f"### {c['id']} — {c['q']}", ""]
            if c.get("error"):
                lines.append(f"- error: `{c['error']}`")
            if c.get("missed_sources"):
                lines.append(f"- thiếu nguồn trong top-5: {c['missed_sources']} · đã lấy: {c['retrieved'][:TOP_K]}")
            if c.get("citations_invalid"):
                lines.append(f"- citation không có trong evidence: {c['citations_invalid']}")
            if "facts" in c:
                lines += [f"- fact `{f}`: {v}" for f, v in c["facts"].items() if v not in ("match", "judge")]
            if c.get("forbidden_asserted"):
                lines += [f"- khẳng định fact cấm `{f}`: {why}" for f, why in c["forbidden_asserted"].items()]
            if "abstain" in c["failures"]:
                lines.append(f"- abstain: kỳ vọng {c['should_abstain']}, thực tế status={c['status']}")
            if c.get("compliance_hits"):
                lines += [f"- vi phạm `{h['pattern']}` ở `{h['field']}`: {h['match']!r}" for h in c["compliance_hits"]]
            if "rule_refs" in c["failures"]:
                lines.append(f"- rule_refs tìm thấy: {c['rule_refs_found']} / {c['rule_refs_total']}")
            if "rubric" in c["failures"]:
                lines += [f"- rubric {k}={v}: {c['rubric_reasons'][k]}" for k, v in c["rubric"].items() if v < 4]
            if c.get("answer_md"):
                lines += ["", "<details><summary>answer</summary>", "", c["answer_md"], "", "</details>"]
    return "\n".join(lines) + "\n"


# ───────────────────────── main ─────────────────────────


def load_cases(path: Path, only: str | None) -> list[dict]:
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if only:
        keys = [k.strip() for k in only.split(",") if k.strip()]
        cases = [c for c in cases if any(c["id"] == k or c["id"].startswith(k) for k in keys)]
    return cases


async def run_all(cases: list[dict], *, concurrency: int, judge: bool) -> list[dict]:
    async with AsyncExitStack() as stack:
        redis = Redis.from_url(settings.redis_url)
        stack.push_async_callback(redis.aclose)
        qdrant = make_client()
        stack.push_async_callback(qdrant.close)
        graph = build_graph(InMemorySaver(), retriever=Retriever(qdrant, embeddings(redis), settings.qdrant_collection))

        print(f"Chạy {len(cases)} case (concurrency={concurrency})…", file=sys.stderr)
        sem = asyncio.Semaphore(concurrency)
        runs = await asyncio.gather(*(run_case(graph, c, sem) for c in cases))
        print("Chấm điểm…", file=sys.stderr)
        return [await score_case(r, judge=judge) for r in runs]


def evaluate(args: argparse.Namespace) -> int:
    cases = load_cases(Path(args.golden), args.only)
    if not cases:
        print("Không có case nào khớp --only", file=sys.stderr)
        return 2
    thresholds = yaml.safe_load(Path(args.thresholds).read_text(encoding="utf-8")) or {}
    baseline_path = Path(args.baseline)
    baseline = json.loads(baseline_path.read_text(encoding="utf-8")) if baseline_path.is_file() else None
    started = datetime.now().isoformat(timespec="seconds")
    results = asyncio.run(run_all(cases, concurrency=args.concurrency, judge=not args.no_judge))

    metrics = aggregate(results)
    checks = check_thresholds(metrics, thresholds)
    report = {
        "meta": {
            "started_at": started,
            "golden": args.golden,
            "judge": not args.no_judge,
            "only": args.only,
            "collection": settings.qdrant_collection,
            "baseline": str(baseline_path) if baseline else None,
        },
        "metrics": metrics,
        "threshold_checks": checks,
        "cases": results,
    }
    out = Path(args.report or EVALS_DIR / "reports" / datetime.now().strftime("%Y-%m-%dT%H-%M"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md = render_md(report, thresholds, baseline)
    out.with_suffix(".md").write_text(md, encoding="utf-8")

    print(md.split("\n## Từng case")[0])
    print(f"Report: {out.with_suffix('.md')} · {out.with_suffix('.json')}")
    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        print(f"❌ Dưới ngưỡng: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Eval độ chính xác ai-service trên golden set")
    p.add_argument("--golden", default=str(EVALS_DIR / "golden_set.jsonl"))
    p.add_argument("--thresholds", default=str(EVALS_DIR / "thresholds.yaml"))
    p.add_argument("--report", default=None, help="đường dẫn report KHÔNG đuôi (mặc định evals/reports/<timestamp>)")
    p.add_argument("--baseline", default=str(EVALS_DIR / "reports" / "baseline.json"))
    p.add_argument("--only", default=None, help="lọc case theo id hoặc tiền tố, cách nhau dấu phẩy: qa-001,cmp-")
    p.add_argument("--concurrency", type=int, default=3)
    p.add_argument("--no-judge", action="store_true", help="bỏ LLM judge (fact fallback, forbidden, rubric)")
    args = p.parse_args()
    settings.require_openai_key()
    code = evaluate(args)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)  # như ai_service.cli: onnxruntime (BM25) có thể abort lúc tắt interpreter trên macOS


if __name__ == "__main__":
    main()
