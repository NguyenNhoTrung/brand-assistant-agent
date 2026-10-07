import pytest

from ai_service.agent.nodes.generate_artifact import normalize_artifact
from ai_service.compliance.deterministic import check, field_texts, strip_quoted
from ai_service.compliance.llm_checker import LLMIssue, ground_issues
from ai_service.compliance.rules import CheckContext, load_rules, rules_prompt

SPF = CheckContext(products=frozenset({"spf50-daily-fluid"}))


def _ids(issues) -> set[str]:
    return {i.rule_id for i in issues}


@pytest.mark.parametrize(
    ("rule_id", "bad", "clean"),
    [
        ("CMP-001", "This serum cures acne in 7 days", "Helps reduce the look of blemishes"),
        ("CMP-002", "Clinically proven to brighten", "Helps brighten the look of dull skin"),
        ("CMP-004", "Results guaranteed!", "Results you can see with consistent use"),
        ("CMP-006", "Black Friday: 40% off everything", "Black Friday: 20% off everything"),
        ("BRD-001", "Fix your skin flaws today", "Give your routine a glow-up"),
    ],
)
def test_pattern_rules_violation_and_clean(rule_id: str, bad: str, clean: str) -> None:
    assert rule_id in _ids(check({"hook": bad}))
    assert rule_id not in _ids(check({"hook": clean}))


def test_required_phrase_spf_missing_and_present() -> None:
    assert "CMP-005" in _ids(check({}, ctx=SPF, required_text="Wear daily."))
    assert "CMP-005" not in _ids(check({}, ctx=SPF, required_text="Reapply every 2 hours and after swimming."))
    # Rule chỉ áp dụng cho sản phẩm SPF
    assert "CMP-005" not in _ids(check({}, ctx=CheckContext(products=frozenset({"vitc-serum-30"})), required_text=""))


def test_testimonial_requires_disclaimer() -> None:
    ctx = CheckContext(content_types=frozenset({"testimonial"}))
    assert "CMP-003" in _ids(check({}, ctx=ctx, required_text=""))
    assert "CMP-003" not in _ids(check({}, ctx=ctx, required_text="Results may vary."))
    assert "CMP-003" not in _ids(check({}, required_text=""))


def test_clinical_claim_allowed_with_study_on_file() -> None:
    assert "CMP-002" not in _ids(
        check({"rtb": "Clinically tested: +68% hydration"}, ctx=CheckContext(clinical_evidence=True))
    )


def test_do_not_say_with_banned_words_is_not_flagged() -> None:
    brief = {
        "single_minded_proposition": "Brighter-looking skin, honestly.",
        "hooks_to_test": [{"text": "Dull mornings? Meet your new glow step.", "source_ids": ["S1"]}],
        "do_not_say": [{"text": "cures acne; clinically proven; guaranteed results", "source_ids": ["S2"]}],
        "compliance_notes": [
            {
                "requested_claim": "cures acne in 7 days",
                "compliant_alternatives": ["Helps reduce the look of blemishes"],
            }
        ],
    }
    texts = field_texts(
        brief, {"single_minded_proposition", "hooks_to_test", "compliance_notes.compliant_alternatives"}
    )
    assert "do_not_say" not in texts
    assert check(texts) == []
    # cùng nội dung nhưng nằm ở field publishable → bị bắt
    brief["hooks_to_test"].append({"text": "It cures acne!", "source_ids": ["S1"]})
    assert "CMP-001" in _ids(check(field_texts(brief, {"hooks_to_test"})))


def test_qa_quotes_and_code_are_ignored() -> None:
    md = 'We cannot say "cures acne" or `clinically proven`.\n> guaranteed results\nIt helps brighten skin [S1].'
    assert check({"answer": strip_quoted(md)}) == []


def test_rules_loaded_and_rendered_for_prompt() -> None:
    rules = load_rules()
    assert {r.id for r in rules} >= {"CMP-001", "CMP-005", "CMP-006", "BRD-001"}
    text = rules_prompt(rules)
    assert "Reapply every 2 hours and after swimming." in text and "CMP-001" in text


def _llm(**kw) -> LLMIssue:
    base = {"reason": "r", "is_violation": True, "kind": "compliance", "rule_id": "CMP-001", "severity": "warn"}
    return LLMIssue(**{**base, "excerpt": "say goodbye to breakouts", "fix_hint": "x", **kw})


def test_llm_issues_grounded_in_content_and_rules() -> None:
    content = "Say goodbye to breakouts forever!"
    out = ground_issues(
        [
            _llm(),  # hợp lệ → severity lấy từ rules.yaml (block), không phải "warn" LLM tự gán
            _llm(excerpt="not in the content at all"),  # ảo giác
            _llm(rule_id="CMP-999"),  # rule không tồn tại
            _llm(is_violation=False),  # góp ý văn phong
        ],
        content,
        load_rules(),
    )
    assert [(i.rule_id, i.severity) for i in out] == [("CMP-001", "block")]


def test_normalize_artifact_moves_inline_markers() -> None:
    a = normalize_artifact(
        {"hooks": [{"text": "Glow up [S2][S3].", "source_ids": ["S2"]}], "alts": ['"Helps brighten [S1]"']}
    )
    assert a["hooks"][0] == {"text": "Glow up.", "source_ids": ["S2", "S3"]}
    assert a["alts"] == ["Helps brighten"]
