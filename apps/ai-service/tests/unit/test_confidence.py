from ai_service.agent.confidence import confidence


def test_sufficient_and_pass_first_time_is_high() -> None:
    assert confidence(grade_status="sufficient", passed=True, revision_count=0, abstained=False) == "high"


def test_partial_or_revised_then_pass_is_medium() -> None:
    assert confidence(grade_status="partial", passed=True, revision_count=0, abstained=False) == "medium"
    assert confidence(grade_status="sufficient", passed=True, revision_count=1, abstained=False) == "medium"


def test_still_failing_after_revisions_is_low() -> None:
    assert confidence(grade_status="sufficient", passed=False, revision_count=2, abstained=False) == "low"


def test_abstain_has_no_confidence() -> None:
    assert confidence(grade_status="insufficient", passed=True, revision_count=0, abstained=True) is None
