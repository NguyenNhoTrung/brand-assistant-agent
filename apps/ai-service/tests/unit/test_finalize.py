from ai_service.agent.nodes.finalize import finalize


def _ev(sid: str, path: str) -> dict:
    return {
        "sid": sid,
        "chunk_id": f"{path}#0",
        "source_path": path,
        "title": path.split("/")[-1],
        "doc_type": "product",
        "section": "Pricing",
        "effective_date": "2026-03-01",
        "text": f"text of {path}",
    }


EVIDENCE = [_ev("S1", "products/a.md"), _ev("S2", "products/b.md"), _ev("S3", "products/c.md")]
PASSED = {"passed": True, "issues": [], "llm_checked": True}


async def test_resolves_and_renumbers_citations() -> None:
    state = {
        "route": {"intent": "qa"},
        "evidence": EVIDENCE,
        "grade": {"status": "sufficient"},
        "draft_md": "Price is $42 [S3]. Texture is light [S1][S3]. Bogus [S9].",
        "verification": PASSED,
        "revision_count": 0,
    }
    out = await finalize(state)
    final = out["final"]
    assert final["answer_md"] == "Price is $42 [1]. Texture is light [2][1]. Bogus."
    assert [(c["n"], c["sid"], c["source_path"]) for c in final["citations"]] == [
        (1, "S3", "products/c.md"),
        (2, "S1", "products/a.md"),
    ]
    assert final["citations"][0]["effective_date"] == "2026-03-01"
    assert final["status"] == "answered" and final["confidence"] == "high"
    assert out["messages"][0].content == final["answer_md"]  # lượt AI vào checkpoint cho hội thoại


async def test_needs_review_when_revisions_exhausted_with_blocking_issue() -> None:
    issue = {"kind": "compliance", "rule_id": "CMP-001", "severity": "block", "excerpt": "cures", "fix_hint": "x"}
    state = {
        "route": {"intent": "qa"},
        "evidence": EVIDENCE,
        "grade": {"status": "sufficient"},
        "draft_md": "It cures acne [S1].",
        "verification": {"passed": False, "issues": [issue], "llm_checked": True},
        "revision_count": 2,
    }
    final = (await finalize(state))["final"]
    assert final["status"] == "needs_review"
    assert final["confidence"] == "low"
    assert final["compliance"]["passed"] is False
    assert final["compliance"]["warnings"][0]["rule_id"] == "CMP-001"


async def test_warn_only_is_answered_with_warning() -> None:
    issue = {"kind": "compliance", "rule_id": "CMP-004", "severity": "warn", "excerpt": "best", "fix_hint": "x"}
    state = {
        "route": {"intent": "qa"},
        "evidence": EVIDENCE,
        "grade": {"status": "partial", "missing_aspects": ["EU shipping"]},
        "draft_md": "Our best serum [S1].",
        "verification": {"passed": False, "issues": [issue], "llm_checked": True},
        "revision_count": 2,
    }
    final = (await finalize(state))["final"]
    assert final["status"] == "partial"
    assert final["compliance"]["passed"] is True and len(final["compliance"]["warnings"]) == 1
    assert final["missing_info"] == ["EU shipping"]


async def test_abstain_has_no_confidence() -> None:
    state = {
        "route": {"intent": "qa"},
        "evidence": EVIDENCE[:1],
        "outcome": "abstained",
        "abstain": {"found": [], "missing": ["EU shipping times"], "suggestion": "ask ops"},
        "draft_md": "**Mình chưa đủ thông tin** [S1]",
    }
    final = (await finalize(state))["final"]
    assert final["status"] == "abstained" and final["confidence"] is None
    assert final["missing_info"] == ["EU shipping times"]
    assert final["answer_md"].endswith("[1]")


async def test_artifact_rendered_and_cited() -> None:
    brief = {
        "title": "SPF brief",
        "objective": {"text": "Grow trial", "source_ids": ["S2"]},
        "target_audience": {"text": "Daily SPF users", "source_ids": ["S2"]},
        "key_insight": {"text": "Hate white cast", "source_ids": ["S2"]},
        "single_minded_proposition": "Daily SPF that disappears",
        "reasons_to_believe": [{"text": "SPF 50", "source_ids": ["S1"]}],
        "tone_and_voice": {"text": "Warm", "source_ids": ["S2"]},
        "mandatory_inclusions": [{"text": "Reapply every 2 hours and after swimming.", "source_ids": ["S1"]}],
        "do_not_say": [],
        "hooks_to_test": [{"text": "No white cast?", "source_ids": ["S2"]}],
        "channels_and_formats": ["Reels"],
        "success_metrics": ["CTR"],
        "open_questions": ["Budget"],
        "compliance_notes": [],
    }
    state = {
        "route": {"intent": "creative_brief"},
        "evidence": EVIDENCE,
        "grade": {"status": "sufficient"},
        "artifact": brief,
        "verification": PASSED,
        "revision_count": 0,
    }
    final = (await finalize(state))["final"]
    assert final["artifact"] == brief
    assert "Reapply every 2 hours and after swimming. [2]" in final["artifact_md"]
    assert "[S" not in final["artifact_md"]
    assert {c["sid"] for c in final["citations"]} == {"S1", "S2"}
    assert "Budget" in final["missing_info"]
