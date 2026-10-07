from ai_service.skills.creative_brief.schema import CreativeBrief
from ai_service.skills.registry import get_skill, registry


def test_registry_discovers_creative_brief() -> None:
    assert "creative_brief" in registry()
    skill = get_skill("creative_brief")
    assert skill is not None and skill.schema is CreativeBrief
    assert get_skill("nope") is None


def test_schema_declares_publishable_fields() -> None:
    skill = get_skill("creative_brief")
    assert skill is not None
    assert {"single_minded_proposition", "hooks_to_test"} <= skill.publishable_fields
    assert "do_not_say" not in skill.publishable_fields
    assert skill.required_phrase_field == "mandatory_inclusions"
    assert set(skill.publishable_fields) - {"compliance_notes.compliant_alternatives"} <= set(
        CreativeBrief.model_fields
    )


def test_retrieval_plan_fills_slots() -> None:
    skill = get_skill("creative_brief")
    assert skill is not None
    queries = dict(skill.queries({"product": "SPF 50 Daily Fluid", "channel": "Instagram Reels", "category": None}))
    assert any("SPF 50 Daily Fluid" in q for q in queries)
    assert any("Instagram Reels" in q for q in queries)
    assert set(skill.doc_types) == {
        "product",
        "customer_research",
        "brand_guideline",
        "compliance",
        "creative_learning",
    }


def test_render_markdown_from_hand_built_brief() -> None:
    def c(text: str, *sids: str) -> dict:
        return {"text": text, "source_ids": list(sids)}

    brief = CreativeBrief(
        title="SPF 50 — Reels",
        objective=c("Drive trial", "S1"),
        target_audience=c("Oily-skin daily commuters", "S2"),
        key_insight=c("Sticky texture is the #1 pain point", "S2"),
        single_minded_proposition="Weightless daily protection.",
        reasons_to_believe=[c("SPF 50 broad spectrum", "S1")],
        tone_and_voice=c("Warm, honest", "S3"),
        mandatory_inclusions=[c("Reapply every 2 hours and after swimming.", "S1")],
        do_not_say=[c("sunblock; waterproof", "S1")],
        hooks_to_test=[c("Sunscreen you forget you're wearing", "S4")],
        channels_and_formats=["Instagram Reels 9:16"],
        success_metrics=["CTR"],
        open_questions=["Budget not in KB"],
        compliance_notes=[],
    ).model_dump()
    md = get_skill("creative_brief").render(brief)  # type: ignore[union-attr]
    assert md.startswith("# SPF 50 — Reels")
    assert "- Reapply every 2 hours and after swimming. [S1]" in md
    assert "1. Sunscreen you forget you're wearing [S4]" in md
    assert "## Open questions" in md and "Compliance notes" not in md
