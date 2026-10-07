import datetime as dt
from pathlib import Path

import pytest

from ai_service.rag.ingest.loader import FrontmatterError, RawDocument, load_file, normalize
from ai_service.rag.ingest.validator import InvalidDocumentError, validate

GOOD = {
    "title": "US Shipping Policy",
    "doc_type": "sop",
    "effective_date": dt.date(2026, 1, 1),
    "version": 2,
}


def _raw(meta: dict, body: str = "## Coverage\n\nUS only.\n", path: str = "sops/x.md") -> RawDocument:
    return RawDocument(source_path=path, meta=meta, body=body, content_hash="h")


def test_valid_document() -> None:
    doc = validate(_raw(GOOD))
    assert (doc.title, doc.doc_type, doc.effective_date, doc.version) == (
        "US Shipping Policy",
        "sop",
        dt.date(2026, 1, 1),
        2,
    )


def test_effective_date_string_is_parsed() -> None:
    assert validate(_raw({**GOOD, "effective_date": "2026-03-01"})).effective_date == dt.date(2026, 3, 1)


def test_missing_doc_type_rejected_with_clear_message() -> None:
    meta = {k: v for k, v in GOOD.items() if k != "doc_type"}
    with pytest.raises(InvalidDocumentError, match=r"sops/x\.md: thiếu `doc_type`"):
        validate(_raw(meta))


def test_unknown_doc_type_lists_allowed_values() -> None:
    with pytest.raises(InvalidDocumentError, match=r"`doc_type` không hợp lệ: 'policy'.*cho phép: brand_guideline"):
        validate(_raw({**GOOD, "doc_type": "policy"}))


@pytest.mark.parametrize("bad", ["2026-13-01", "next monday", "01/03/2026", 20260301])
def test_bad_effective_date_rejected(bad: object) -> None:
    with pytest.raises(InvalidDocumentError, match="`effective_date` không phải ngày YYYY-MM-DD"):
        validate(_raw({**GOOD, "effective_date": bad}))


def test_missing_effective_date_rejected() -> None:
    meta = {k: v for k, v in GOOD.items() if k != "effective_date"}
    with pytest.raises(InvalidDocumentError, match="thiếu `effective_date`"):
        validate(_raw(meta))


def test_all_problems_reported_at_once() -> None:
    with pytest.raises(InvalidDocumentError) as e:
        validate(_raw({"doc_type": "product", "effective_date": "soon", "version": 0}))
    assert len(e.value.problems) == 4  # title, effective_date, version, product_id


def test_product_requires_product_id_and_supersedes_must_be_md() -> None:
    with pytest.raises(InvalidDocumentError, match="product_id"):
        validate(_raw({**GOOD, "doc_type": "product"}))
    with pytest.raises(InvalidDocumentError, match="supersedes"):
        validate(_raw({**GOOD, "supersedes": "old-doc"}))


def test_empty_body_rejected() -> None:
    with pytest.raises(InvalidDocumentError, match="nội dung rỗng"):
        validate(_raw(GOOD, body="\n"))


def test_loader_requires_frontmatter(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# No frontmatter\n")
    with pytest.raises(FrontmatterError, match=r"a\.md: thiếu frontmatter"):
        load_file(tmp_path / "a.md", tmp_path)


def test_loader_parses_and_hashes(tmp_path: Path) -> None:
    (tmp_path / "sops").mkdir()
    f = tmp_path / "sops" / "a.md"
    f.write_text("---\ntitle: A\ndoc_type: sop\neffective_date: 2026-01-01\nversion: 1\n---\n\n## S\n\ntext\n")
    raw = load_file(f, tmp_path)
    assert raw.source_path == "sops/a.md"
    assert raw.meta["effective_date"] == dt.date(2026, 1, 1)
    assert raw.body.startswith("## S")
    h1 = raw.content_hash
    f.write_text(f.read_text().replace("version: 1", "version: 2"))
    assert load_file(f, tmp_path).content_hash != h1  # đổi frontmatter cũng là đổi


def test_normalize_tables_and_whitespace() -> None:
    text = "| Method | Time |\n|---|:---:|\n| Standard | 2–5 days |\n\n\n\nafter   \n"
    assert normalize(text) == "- Method: Standard; Time: 2–5 days\n\nafter\n"
    assert normalize("Café") == "Café\n"  # NFC
