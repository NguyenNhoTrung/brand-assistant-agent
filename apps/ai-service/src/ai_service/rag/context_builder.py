"""Chunk đã xếp hạng → evidence `S1..Sn` + khối `<source>` cho prompt (§9.8, §10.4).

- Ngân sách ~6k token; vượt thì ưu tiên chunk hạng cao.
- Mỗi doc_type yêu cầu (mặc định: mọi doc_type có trong kết quả) được giữ ≥ 1 chunk.
- Nội dung trong `<source>` là DỮ LIỆU — thẻ đóng giả trong nội dung bị vô hiệu hoá.
"""

import html
import re
from dataclasses import asdict, dataclass
from typing import Any

from ai_service.rag.retriever import RetrievedChunk
from ai_service.rag.tokens import count_tokens

CONTEXT_BUDGET_TOKENS = 6000

_TAG_ESCAPE = re.compile(r"<(/?)source", re.IGNORECASE)


@dataclass(frozen=True)
class Evidence:
    sid: str
    chunk_id: str
    source_path: str
    title: str
    doc_type: str
    section: str
    effective_date: str
    text: str
    product_id: str | None = None
    has_clinical_studies: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextPack:
    evidence: list[Evidence]
    text: str  # các khối <source> nối nhau — đưa thẳng vào prompt
    tokens: int


def render_source(e: Evidence) -> str:
    def attr(v: str) -> str:
        return html.escape(v, quote=True)

    body = _TAG_ESCAPE.sub(r"&lt;\1source", e.text.strip())
    return (
        f'<source id="{e.sid}" doc="{attr(e.title)}" section="{attr(e.section)}" '
        f'type="{e.doc_type}" effective="{e.effective_date}">\n{body}\n</source>'
    )


def _evidence(sid: str, c: RetrievedChunk) -> Evidence:
    return Evidence(
        sid=sid,
        chunk_id=c.chunk_id,
        source_path=c.source_path,
        title=c.title,
        doc_type=c.doc_type,
        section=c.section,
        effective_date=c.effective_date,
        text=c.content,
        product_id=c.product_id,
        has_clinical_studies=c.has_clinical_studies,
    )


def build_context(
    chunks: list[RetrievedChunk],
    *,
    budget_tokens: int = CONTEXT_BUDGET_TOKENS,
    required_doc_types: list[str] | None = None,
) -> ContextPack:
    """`chunks` đã xếp hạng (tốt nhất trước). Trả evidence đánh số S1..Sn liên tục theo thứ hạng."""
    cost = [count_tokens(render_source(_evidence("S0", c))) for c in chunks]

    # 1. Giữ chunk hạng cao nhất của mỗi doc_type yêu cầu — kể cả khi phải vượt ngân sách
    wanted = required_doc_types if required_doc_types is not None else [c.doc_type for c in chunks]
    keep: set[int] = set()
    for dt in dict.fromkeys(wanted):
        first = next((i for i, c in enumerate(chunks) if c.doc_type == dt), None)
        if first is not None:
            keep.add(first)
    used = sum(cost[i] for i in keep)

    # 2. Lấp phần còn lại theo thứ hạng trong ngân sách
    for i in range(len(chunks)):
        if i not in keep and used + cost[i] <= budget_tokens:
            keep.add(i)
            used += cost[i]

    evidence = [_evidence(f"S{n}", chunks[i]) for n, i in enumerate(sorted(keep), start=1)]
    text = "\n\n".join(render_source(e) for e in evidence)
    return ContextPack(evidence=evidence, text=text, tokens=count_tokens(text) if text else 0)
