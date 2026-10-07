"""Kiểm tra frontmatter trước khi ingest — file lỗi bị từ chối với thông báo rõ (§10.2)."""

import datetime as dt
from dataclasses import dataclass
from typing import Any, Literal, get_args

from ai_service.rag.ingest.loader import RawDocument

DocType = Literal["product", "brand_guideline", "compliance", "sop", "customer_research", "creative_learning"]
DOC_TYPES: frozenset[str] = frozenset(get_args(DocType))


@dataclass(frozen=True)
class Document:
    source_path: str
    title: str
    doc_type: str
    effective_date: dt.date
    version: int
    body: str
    content_hash: str
    meta: dict[str, Any]

    @property
    def supersedes(self) -> str | None:
        return self.meta.get("supersedes")


class InvalidDocumentError(ValueError):
    def __init__(self, source_path: str, problems: list[str]) -> None:
        self.source_path, self.problems = source_path, problems
        super().__init__(f"{source_path}: " + "; ".join(problems))


def _parse_date(v: Any) -> dt.date | None:
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if isinstance(v, str):
        try:
            return dt.date.fromisoformat(v.strip())
        except ValueError:
            return None
    return None


def validate(raw: RawDocument) -> Document:
    """Trả Document hợp lệ, hoặc raise InvalidDocumentError liệt kê MỌI lỗi một lần."""
    m, problems = raw.meta, []

    title = m.get("title")
    if not isinstance(title, str) or not title.strip():
        problems.append("thiếu `title`")

    doc_type = m.get("doc_type")
    if doc_type is None:
        problems.append("thiếu `doc_type`")
    elif doc_type not in DOC_TYPES:
        problems.append(f"`doc_type` không hợp lệ: {doc_type!r} (cho phép: {', '.join(sorted(DOC_TYPES))})")

    eff = _parse_date(m.get("effective_date"))
    if "effective_date" not in m:
        problems.append("thiếu `effective_date`")
    elif eff is None:
        problems.append(f"`effective_date` không phải ngày YYYY-MM-DD: {m['effective_date']!r}")

    version = m.get("version", 1)
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        problems.append(f"`version` phải là số nguyên ≥ 1: {version!r}")

    if doc_type == "product" and not m.get("product_id"):
        problems.append("tài liệu `product` phải có `product_id`")

    sup = m.get("supersedes")
    if sup is not None and (not isinstance(sup, str) or not sup.endswith(".md")):
        problems.append(f"`supersedes` phải là đường dẫn .md tương đối với thư mục KB: {sup!r}")
    if sup == raw.source_path:
        problems.append("`supersedes` không được trỏ vào chính nó")

    if not raw.body.strip():
        problems.append("nội dung rỗng")

    if problems:
        raise InvalidDocumentError(raw.source_path, problems)
    assert isinstance(title, str) and isinstance(doc_type, str) and eff is not None
    return Document(
        source_path=raw.source_path,
        title=title.strip(),
        doc_type=doc_type,
        effective_date=eff,
        version=version,
        body=raw.body,
        content_hash=raw.content_hash,
        meta=m,
    )
