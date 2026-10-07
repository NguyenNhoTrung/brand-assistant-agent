from pathlib import Path

import pytest

from ai_service.rag.ingest.chunker import MAX_TOKENS, chunk_document
from ai_service.rag.ingest.loader import load_file
from ai_service.rag.ingest.validator import validate
from ai_service.rag.tokens import count_tokens

KB_DIR = Path(__file__).resolve().parents[4] / "data" / "knowledge"

BODY = """# Brand Voice Guidelines

Intro line before any section.

## Tone

We sound like a knowledgeable friend.

### Do

- Be warm.

### Don't

- Shame people.

## Preferred Words

Use "glow", avoid "flawless".
""" + " ".join(["glow"] * 80)  # đủ dài để không bị gộp như mẩu đuôi


def _para(n: int, word: str) -> str:
    return " ".join([word] * n)


def test_small_doc_cuts_at_headings_with_context_header() -> None:
    chunks = chunk_document("Brand Voice Guidelines", BODY, min_tokens=1)  # min=1 → mỗi section một chunk
    assert [c.heading_path for c in chunks] == [(), ("Tone",), ("Tone", "Do"), ("Tone", "Don't"), ("Preferred Words",)]
    assert chunks[3].context_header == "Brand Voice Guidelines › Tone › Don't"
    assert chunks[3].content.startswith("### Don't")
    assert chunks[3].embed_text.startswith("Brand Voice Guidelines › Tone › Don't\n\n")
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))
    assert "# Brand Voice Guidelines" not in "".join(c.content for c in chunks)  # H1 = tiêu đề, không lặp


def test_small_sections_merged_header_lists_branches() -> None:
    chunks = chunk_document("Brand Voice Guidelines", BODY)  # tất cả < 300 token → một chunk
    assert len(chunks) == 1
    assert chunks[0].context_header == "Brand Voice Guidelines › Tone · Preferred Words"
    sub = chunk_document("D", "## Tone\n\n### Do\n\nx\n\n### Don't\n\ny\n")
    assert sub[0].heading_path == ("Tone", "Do · Don't")


def test_boundaries_only_at_headings_when_sections_fit() -> None:
    body = "\n\n".join(f"## S{i}\n\n{_para(250, 'alpha')}" for i in range(4))
    chunks = chunk_document("Doc", body)
    for c in chunks:
        assert c.content.startswith("## S")  # không chunk nào bắt đầu giữa section
        assert c.token_count <= MAX_TOKENS
    assert sum(c.content.count("## S") for c in chunks) == 4


def test_long_section_split_with_overlap_and_token_limit() -> None:
    paras = [f"Paragraph {i}. " + _para(120, f"w{i}") for i in range(12)]
    chunks = chunk_document("Doc", "## Long\n\n" + "\n\n".join(paras))
    assert len(chunks) > 1
    assert all(c.token_count <= MAX_TOKENS for c in chunks)
    assert all(c.heading_path == ("Long",) for c in chunks)
    assert chunks[1].content.startswith("…")  # overlap từ mảnh trước
    first_tail_word = chunks[0].content.split()[-1]
    assert first_tail_word in chunks[1].content.split("\n\n")[0]


def test_single_giant_paragraph_is_hard_split() -> None:
    chunks = chunk_document("Doc", "## Wall\n\n" + _para(3000, "lorem"))
    assert len(chunks) >= 5
    assert all(count_tokens(c.content) <= MAX_TOKENS for c in chunks)


def test_heading_inside_code_fence_is_not_a_section() -> None:
    chunks = chunk_document("Doc", "## Real\n\n```\n## not a heading\n```\n", min_tokens=1)
    assert [c.heading_path for c in chunks] == [("Real",)]


def test_tiny_tail_merged_into_previous() -> None:
    body = f"## A\n\n{_para(320, 'a')}\n\n## B\n\nshort tail"
    chunks = chunk_document("Doc", body)
    assert len(chunks) == 1 and chunks[0].heading_path == ("A · B",)


@pytest.mark.parametrize("path", sorted(KB_DIR.rglob("*.md")), ids=lambda p: p.relative_to(KB_DIR).as_posix())
def test_real_kb_chunks_within_limit(path: Path) -> None:
    doc = validate(load_file(path, KB_DIR))
    chunks = chunk_document(doc.title, doc.body)
    assert chunks
    assert all(0 < c.token_count <= MAX_TOKENS for c in chunks)
    assert all(c.context_header.startswith(doc.title) for c in chunks)
