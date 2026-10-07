from ai_service.agent.edges import MAX_RETRIEVAL_ATTEMPTS, MAX_REVISIONS, after_grade, after_route, after_verify


def _grade(status: str, rewrite: str | None = None) -> dict:
    return {
        "status": status,
        "relevant_sids": [],
        "covered_aspects": [],
        "missing_aspects": [],
        "rewrite_query": rewrite,
    }


def test_route_out_of_scope_or_clarify_goes_direct() -> None:
    assert after_route({"route": {"intent": "out_of_scope"}}) == "respond_direct"
    assert after_route({"route": {"intent": "qa", "needs_clarification": True}}) == "respond_direct"
    assert after_route({"route": {"intent": "qa", "needs_clarification": False}}) == "plan_retrieval"
    assert after_route({"route": {"intent": "creative_brief"}}) == "plan_retrieval"


def test_insufficient_with_attempts_left_retries() -> None:
    s = {"route": {"intent": "qa"}, "grade": _grade("insufficient", "eu shipping"), "retrieval_attempts": 1}
    assert after_grade(s) == "retrieve"


def test_insufficient_out_of_attempts_abstains() -> None:
    s = {
        "route": {"intent": "qa"},
        "grade": _grade("insufficient", "eu shipping"),
        "retrieval_attempts": MAX_RETRIEVAL_ATTEMPTS,
    }
    assert after_grade(s) == "abstain"


def test_insufficient_without_rewrite_abstains() -> None:
    s = {"route": {"intent": "qa"}, "grade": _grade("insufficient"), "retrieval_attempts": 1}
    assert after_grade(s) == "abstain"


def test_artifact_intent_goes_to_generate_artifact() -> None:
    for status in ("sufficient", "partial"):
        assert after_grade({"route": {"intent": "creative_brief"}, "grade": _grade(status)}) == "generate_artifact"
        assert after_grade({"route": {"intent": "qa"}, "grade": _grade(status)}) == "generate_answer"


def test_verify_fail_revises_until_limit_then_finalizes() -> None:
    failed = {"passed": False, "issues": []}
    assert after_verify({"verification": failed, "revision_count": 0}) == "revise"
    assert after_verify({"verification": failed, "revision_count": 1}) == "revise"
    assert after_verify({"verification": failed, "revision_count": MAX_REVISIONS}) == "finalize"
    assert after_verify({"verification": {"passed": True, "issues": []}, "revision_count": 0}) == "finalize"
