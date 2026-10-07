"""verify = deterministic (compliance theo field + citation) + LLM verifier (§9.4, §10.5, §11.2)."""

import re
from typing import Any

from ai_service.agent.nodes._common import emit, intent, is_artifact, sources_block, started
from ai_service.agent.prompts import load_prompt
from ai_service.agent.schemas import Issue, VerificationReport
from ai_service.agent.state import AgentState
from ai_service.compliance import deterministic
from ai_service.compliance.llm_checker import llm_check
from ai_service.compliance.rules import CheckContext, load_rules, rules_prompt
from ai_service.rag.citations import validate_citations
from ai_service.skills.registry import Skill, get_skill

_FACTUAL = re.compile(r"\d")  # số, giá, %, cỡ mẫu, ngày → phải có nguồn
_TESTIMONIAL = re.compile(r"\btestimonials?\b", re.IGNORECASE)
_BEFORE_AFTER = re.compile(r"\bbefore[\s/-]*(?:and[\s-]*)?after\b", re.IGNORECASE)


def missing_citations(md: str) -> list[Issue]:
    """Dòng có nội dung factual (chứa số) mà không có marker [S#] → `missing_citation`."""
    issues = []
    for raw in deterministic.strip_quoted(md).splitlines():
        line = raw.strip()
        if len(line) < 20 or line.startswith(("#", "|---", "---")) or not _FACTUAL.search(line):
            continue
        if not re.search(r"\[\s*S\d+", line):
            issues.append(
                Issue(
                    kind="missing_citation",
                    excerpt=line[:160],
                    fix_hint="Add the [S#] marker of the supporting source, or remove the statement",
                )
            )
    return issues


def _cited_items(artifact: dict[str, Any], fields: tuple[str, ...]) -> list[tuple[str, dict[str, Any]]]:
    out = []
    for f in fields:
        v = artifact.get(f)
        for item in v if isinstance(v, list) else [v]:
            if isinstance(item, dict) and "source_ids" in item:
                out.append((f, item))
    return out


def artifact_citation_issues(artifact: dict[str, Any], skill: Skill, valid_sids: set[str]) -> list[Issue]:
    issues = []
    fields = tuple(getattr(skill.schema, "CITED_FIELDS", ()))
    for field, item in _cited_items(artifact, fields):
        if not item["source_ids"]:
            issues.append(
                Issue(kind="missing_citation", excerpt=f"[{field}] {item['text'][:120]}", fix_hint="Add source_ids")
            )
        for sid in item["source_ids"]:
            if sid not in valid_sids:
                issues.append(
                    Issue(
                        kind="invalid_citation",
                        excerpt=f"[{field}] {sid}",
                        fix_hint=f"{sid} is not a provided source; use a valid sid",
                    )
                )
    return issues


FACT_FIELDS = ("key_insight", "reasons_to_believe", "hooks_to_test")


def artifact_check_content(artifact: dict[str, Any], publishable: dict[str, str]) -> str:
    """Phần đưa cho LLM verifier: field publishable (compliance) + claim factual kèm sid đã trích (support)."""
    lines = [f"[{k}]\n{v}" for k, v in publishable.items() if v]
    for field, item in _cited_items(artifact, FACT_FIELDS):
        lines.append(f"[{field}] {item['text']} (cited: {', '.join(item['source_ids']) or 'none'})")
    return "\n".join(lines)


def check_context(state: AgentState, cited: set[str] | None = None) -> CheckContext:
    """Sản phẩm trong bối cảnh = product sheet được trích dẫn (artifact) hoặc có trong evidence (Q&A)."""
    products = [
        e
        for e in state.get("evidence", [])
        if e["doc_type"] == "product" and e.get("product_id") and (cited is None or e["sid"] in cited)
    ]
    return CheckContext(
        products=frozenset(e["product_id"] for e in products),
        clinical_evidence=any(e.get("has_clinical_studies") for e in products),
    )


def _dedupe(issues: list[Issue]) -> list[Issue]:
    seen: dict[tuple[str, str | None, str], Issue] = {}
    for i in issues:
        seen.setdefault((i.kind, i.rule_id, i.excerpt.strip().lower()), i)
    return list(seen.values())


async def verify(state: AgentState) -> dict:
    started("verify", "Đang kiểm tra compliance và trích dẫn")
    evidence = state.get("evidence", [])
    valid_sids = {e["sid"] for e in evidence}
    rules = load_rules()

    if is_artifact(state):
        skill = get_skill(intent(state))
        assert skill is not None
        artifact = state.get("artifact") or {}
        cited = {s for _, item in _cited_items(artifact, tuple(skill.schema.model_fields)) for s in item["source_ids"]}
        ctx = check_context(state, cited)
        texts = deterministic.field_texts(artifact, skill.publishable_fields)
        scan = " ".join([*texts.values(), *map(str, artifact.get("channels_and_formats", []))])
        content_types = {"testimonial"} if _TESTIMONIAL.search(scan) else set()
        if _BEFORE_AFTER.search(scan):
            content_types.add("before_after")
        ctx = CheckContext(ctx.products, frozenset(content_types), ctx.clinical_evidence)
        required = None
        if skill.required_phrase_field:
            required = deterministic.field_texts(artifact, [skill.required_phrase_field])[skill.required_phrase_field]
        issues = deterministic.check(texts, rules, ctx, required_text=required)
        issues += artifact_citation_issues(artifact, skill, valid_sids)
        content = artifact_check_content(artifact, texts)
    else:
        draft = state.get("draft_md") or ""
        issues = deterministic.check({"answer": deterministic.strip_quoted(draft)}, rules, check_context(state))
        issues += [
            Issue(kind="invalid_citation", excerpt=c.sid, fix_hint=c.message)
            for c in validate_citations(draft, evidence)
        ]
        issues += missing_citations(draft)
        content = draft

    llm_issues = await llm_check(
        system_prompt=load_prompt("verify").render(rules=rules_prompt(rules)),
        content=content,
        sources=sources_block(evidence),
        rules=rules,
    )
    issues = _dedupe(issues + (llm_issues or []))
    report = VerificationReport(passed=not issues, issues=issues, llm_checked=llm_issues is not None)
    emit(
        "verification.result",
        {
            "passed": report.passed,
            "issues": [i.model_dump() for i in issues],
            "revision": state.get("revision_count", 0),
        },
    )
    return {"verification": report.model_dump()}
