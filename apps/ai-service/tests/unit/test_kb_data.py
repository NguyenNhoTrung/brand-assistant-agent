"""Kiểm tra dữ liệu mẫu (Bước 2): frontmatter KB, rules compliance, golden set — không cần LLM/hạ tầng."""

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[4]
KB_DIR = ROOT / "data" / "knowledge"
RULES_PATH = ROOT / "data" / "compliance" / "rules.yaml"
GOLDEN_PATH = ROOT / "evals" / "golden_set.jsonl"

DOC_TYPES = {"product", "brand_guideline", "compliance", "sop", "customer_research", "creative_learning"}
KB_FILES = sorted(KB_DIR.rglob("*.md"))


def _frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, f"{path}: thiếu frontmatter"
    meta = yaml.safe_load(m.group(1))
    assert isinstance(meta, dict), f"{path}: frontmatter không phải mapping"
    return meta


def _rel(path: Path) -> str:
    return path.relative_to(KB_DIR).as_posix()


def test_kb_has_enough_files() -> None:
    assert len(KB_FILES) >= 17


@pytest.mark.parametrize("path", KB_FILES, ids=_rel)
def test_frontmatter_valid(path: Path) -> None:
    meta = _frontmatter(path)
    assert isinstance(meta.get("title"), str) and meta["title"].strip()
    assert meta.get("doc_type") in DOC_TYPES
    eff = meta.get("effective_date")
    if isinstance(eff, str):
        eff = dt.date.fromisoformat(eff)
    assert isinstance(eff, dt.date)
    assert isinstance(meta.get("version"), int) and meta["version"] >= 1
    if meta["doc_type"] == "product":
        assert meta.get("product_id")
    if sup := meta.get("supersedes"):
        assert (KB_DIR / sup).is_file(), f"supersedes trỏ tới file không tồn tại: {sup}"


def test_every_doc_type_covered() -> None:
    assert {_frontmatter(p)["doc_type"] for p in KB_FILES} == DOC_TYPES


def test_rules_valid() -> None:
    data = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))
    rules = data["rules"]
    ids = [r["id"] for r in rules]
    assert len(ids) == len(set(ids))
    assert {"CMP-001", "CMP-002", "CMP-003", "CMP-004", "CMP-005", "CMP-006", "BRD-001"} <= set(ids)
    for r in rules:
        assert r["severity"] in {"block", "warn"}, r["id"]
        for pat in r.get("patterns", []):
            re.compile(pat)


def test_golden_set_valid() -> None:
    lines = [ln for ln in GOLDEN_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) >= 20
    cases = [json.loads(ln) for ln in lines]
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids))
    for c in cases:
        assert c["q"].strip(), c["id"]
        for src in c.get("expected_sources", []):
            assert (KB_DIR / src).is_file(), f"{c['id']}: nguồn không tồn tại {src}"
        for pat in c.get("forbidden_patterns", []):
            re.compile(pat)
