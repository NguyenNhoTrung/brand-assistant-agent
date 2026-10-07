"""Citation `[S#]`: parse, validate theo evidence của lượt, resolve → `[1] [2]…` (§10.5)."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from shared.contracts import Citation

# [S1] · [S1][S3] · [S1, S3] · [S1; S3]
_GROUP = re.compile(r"([ \t]?)\[\s*(S\d+(?:\s*[,;]\s*S\d+)*)\s*\]")
_SID = re.compile(r"S\d+")
SNIPPET_CHARS = 240


class ResolvedCitation(Citation):
    """= `Citation` của contract (đã có `source_path`, `effective_date`) — giữ tên theo §9.6."""


@dataclass(frozen=True)
class CitationIssue:
    code: str  # invalid_citation
    sid: str
    message: str


def parse_citations(text: str) -> list[str]:
    """Các sid theo thứ tự xuất hiện lần đầu, không trùng."""
    seen: dict[str, None] = {}
    for m in _GROUP.finditer(text):
        for sid in _SID.findall(m.group(2)):
            seen.setdefault(sid)
    return list(seen)


def _get(e: Any, key: str) -> Any:
    return e[key] if isinstance(e, Mapping) else getattr(e, key)


def _opt(e: Any, key: str) -> str:
    return str((e.get(key) if isinstance(e, Mapping) else getattr(e, key, None)) or "")


def validate_citations(text: str, evidence: Sequence[Any]) -> list[CitationIssue]:
    """Mọi sid được trích phải thuộc evidence của lượt này."""
    valid = {_get(e, "sid") for e in evidence}
    return [
        CitationIssue("invalid_citation", sid, f"{sid} không có trong evidence của lượt này")
        for sid in parse_citations(text)
        if sid not in valid
    ]


def resolve_citations(text: str, evidence: Sequence[Any]) -> tuple[str, list[ResolvedCitation]]:
    """`[S3] … [S1][S3]` → `[1] … [2][1]`; sid không hợp lệ bị bỏ khỏi văn bản."""
    by_sid = {_get(e, "sid"): e for e in evidence}
    number: dict[str, int] = {}
    citations: list[ResolvedCitation] = []

    def repl(m: re.Match[str]) -> str:
        out = []
        for sid in dict.fromkeys(_SID.findall(m.group(2))):
            e = by_sid.get(sid)
            if e is None:
                continue
            if sid not in number:
                number[sid] = len(number) + 1
                snippet = " ".join(str(_get(e, "text")).split())
                citations.append(
                    ResolvedCitation(
                        n=number[sid],
                        sid=sid,
                        chunk_id=_get(e, "chunk_id"),
                        title=_get(e, "title"),
                        section=_get(e, "section") or "",
                        snippet=snippet[:SNIPPET_CHARS] + ("…" if len(snippet) > SNIPPET_CHARS else ""),
                        source_path=_opt(e, "source_path"),
                        effective_date=_opt(e, "effective_date"),
                    )
                )
            out.append(f"[{number[sid]}]")
        return m.group(1) + "".join(out) if out else ""  # marker bị bỏ → bỏ luôn dấu cách đứng trước

    return _GROUP.sub(repl, text), citations
