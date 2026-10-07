from ai_service.rag.citations import parse_citations, resolve_citations, validate_citations
from ai_service.rag.context_builder import Evidence

EVIDENCE = [
    Evidence(
        sid=f"S{i}",
        chunk_id=f"doc{i}.md#0",
        source_path=f"doc{i}.md",
        title=f"Doc {i}",
        doc_type="product",
        section="Pricing",
        effective_date="2026-03-01",
        text=f"Content of doc {i}. " * 30,
    )
    for i in range(1, 4)
]


def test_parse_adjacent_and_grouped_markers_in_order() -> None:
    assert parse_citations("Price is $42 [S3][S1]. Texture [S2, S3]; old [S1].") == ["S3", "S1", "S2"]
    assert parse_citations("no markers, [1], [s2], [Source 1]") == []


def test_sid_outside_evidence_is_invalid_citation() -> None:
    issues = validate_citations("A [S1]. B [S7]. C [S2][S9].", EVIDENCE)
    assert [(i.code, i.sid) for i in issues] == [("invalid_citation", "S7"), ("invalid_citation", "S9")]
    assert validate_citations("A [S1][S3].", EVIDENCE) == []


def test_validate_accepts_dict_evidence() -> None:
    assert validate_citations("x [S1]", [{"sid": "S1"}]) == []


def test_resolve_renumbers_by_order_of_appearance() -> None:
    text, cits = resolve_citations("Price $42 [S3]. Texture [S1][S3]. Again [S1, S2].", EVIDENCE)
    assert text == "Price $42 [1]. Texture [2][1]. Again [2][3]."
    assert [(c.n, c.sid, c.chunk_id, c.source_path) for c in cits] == [
        (1, "S3", "doc3.md#0", "doc3.md"),
        (2, "S1", "doc1.md#0", "doc1.md"),
        (3, "S2", "doc2.md#0", "doc2.md"),
    ]
    assert cits[0].title == "Doc 3" and cits[0].section == "Pricing"
    assert len(cits[0].snippet) <= 241 and cits[0].snippet.endswith("…")


def test_resolve_drops_invalid_markers() -> None:
    text, cits = resolve_citations("Fact [S9]. Other [S2][S8].\n\n  indented [S1]", EVIDENCE)
    assert text == "Fact. Other [1].\n\n  indented [2]"
    assert [c.sid for c in cits] == ["S2", "S1"]
