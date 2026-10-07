"""Chunk theo heading Markdown (§10.2).

1. Tách body thành section theo heading `##`..`######` (H1 là tiêu đề tài liệu → bỏ).
2. Section dài hơn `max_tokens` → cắt theo đoạn văn, mảnh sau mang `overlap` token cuối của mảnh trước.
3. Gộp các section liền kề cho tới khi đạt `min_tokens`, không bao giờ vượt `max_tokens`
   → ranh giới chunk luôn nằm ở heading (trừ section quá dài).
4. Header ngữ cảnh `Doc › Section › Sub` ghép trước nội dung khi embed.
"""

import itertools
import re
from dataclasses import dataclass

from ai_service.rag.tokens import count_tokens, split_tokens, tail_tokens

MIN_TOKENS = 300
MAX_TOKENS = 700
OVERLAP_TOKENS = 60
MIN_TAIL_TOKENS = 60
SEP = " › "

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    heading_path: tuple[str, ...]  # ("Tone", "Do · Don't") — không gồm tên tài liệu
    context_header: str  # "Brand Voice Guidelines › Tone › Do · Don't"
    content: str
    token_count: int

    @property
    def section(self) -> str:
        return SEP.join(self.heading_path)

    @property
    def embed_text(self) -> str:
        return f"{self.context_header}\n\n{self.content}"


@dataclass(frozen=True)
class _Unit:
    path: tuple[str, ...]
    text: str


def _sections(body: str) -> list[_Unit]:
    units: list[_Unit] = []
    stack: list[tuple[int, str]] = []  # (level, heading) cho H2..H6
    buf: list[str] = []
    in_fence = False

    def flush() -> None:
        text = "\n".join(buf).strip()
        if text:
            units.append(_Unit(tuple(h for _, h in stack), text))
        buf.clear()

    for line in body.split("\n"):
        if _FENCE.match(line):
            in_fence = not in_fence
        m = None if in_fence else _HEADING.match(line)
        if m is None:
            buf.append(line)
            continue
        flush()
        level, heading = len(m.group(1)), m.group(2).strip()
        if level == 1:
            stack.clear()
            continue
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, heading))
        buf.append(line)
    flush()
    return units


def _split_long(unit: _Unit, max_tokens: int, overlap: int) -> list[_Unit]:
    """Section quá dài → mảnh ≤ max_tokens (kể cả phần overlap), cắt ở ranh giới đoạn văn."""
    if count_tokens(unit.text) <= max_tokens:
        return [unit]
    budget = max_tokens - overlap - 8  # chừa chỗ cho "…" + xuống dòng nối overlap
    paras: list[str] = []
    for p in re.split(r"\n\s*\n", unit.text):
        paras.extend([p] if count_tokens(p) <= budget else split_tokens(p, budget))
    pieces: list[str] = []
    cur: list[str] = []
    for p in paras:
        if cur and count_tokens("\n\n".join([*cur, p])) > budget:
            pieces.append("\n\n".join(cur))
            cur = []
        cur.append(p)
    if cur:
        pieces.append("\n\n".join(cur))
    out = [pieces[0]]
    for prev, piece in itertools.pairwise(pieces):
        out.append(f"…{tail_tokens(prev, overlap).lstrip()}\n\n{piece}")
    return [_Unit(unit.path, text) for text in out]


def _label(paths: list[tuple[str, ...]]) -> tuple[str, ...]:
    """Đường dẫn heading của một chunk gộp nhiều section: phần chung + các nhánh nối bằng ' · '."""
    paths = [p for p in paths if p] or [()]
    prefix: list[str] = []
    for parts in zip(*paths, strict=False):
        if len(set(parts)) != 1:
            break
        prefix.append(parts[0])
    rest = list(dict.fromkeys(p[len(prefix)] for p in paths if len(p) > len(prefix)))
    return (*prefix, " · ".join(rest)) if rest else tuple(prefix)


def chunk_document(
    title: str,
    body: str,
    *,
    min_tokens: int = MIN_TOKENS,
    max_tokens: int = MAX_TOKENS,
    overlap: int = OVERLAP_TOKENS,
) -> list[Chunk]:
    units = [piece for u in _sections(body) for piece in _split_long(u, max_tokens, overlap)]

    groups: list[list[_Unit]] = []
    cur: list[_Unit] = []
    for u in units:
        if cur:
            cur_tokens = count_tokens("\n\n".join(x.text for x in cur))
            merged_tokens = count_tokens("\n\n".join(x.text for x in [*cur, u]))
            if cur_tokens >= min_tokens or merged_tokens > max_tokens:
                groups.append(cur)
                cur = []
        cur.append(u)
    if cur:
        groups.append(cur)
    # Mẩu đuôi lẻ (vd. một mục cuối 20 token) → gộp vào chunk trước nếu vẫn trong giới hạn
    if len(groups) > 1:
        tail = count_tokens("\n\n".join(u.text for u in groups[-1]))
        merged = count_tokens("\n\n".join(u.text for u in [*groups[-2], *groups[-1]]))
        if tail < MIN_TAIL_TOKENS and merged <= max_tokens:
            groups[-2:] = [[*groups[-2], *groups[-1]]]

    chunks = []
    for i, g in enumerate(groups):
        path = _label([u.path for u in g])
        content = "\n\n".join(u.text for u in g)
        chunks.append(
            Chunk(
                ordinal=i,
                heading_path=path,
                context_header=SEP.join([title, *path]),
                content=content,
                token_count=count_tokens(content),
            )
        )
    return chunks
