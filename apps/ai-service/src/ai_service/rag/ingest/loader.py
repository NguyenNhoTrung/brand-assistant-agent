"""Đọc file Markdown → frontmatter + body đã normalize (§10.2)."""

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_TABLE_SEP = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$")


@dataclass(frozen=True)
class RawDocument:
    source_path: str  # tương đối với thư mục KB, dạng posix: "products/vitamin-c-serum.md"
    meta: dict[str, Any]
    body: str
    content_hash: str  # sha256 của toàn bộ file (đổi frontmatter cũng tính là đổi)


class FrontmatterError(ValueError):
    pass


def load_file(path: Path, root: Path) -> RawDocument:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    source_path = path.relative_to(root).as_posix()
    m = _FRONTMATTER.match(text)
    if not m:
        raise FrontmatterError(f"{source_path}: thiếu frontmatter YAML (khối --- ... --- ở đầu file)")
    try:
        meta = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        raise FrontmatterError(f"{source_path}: frontmatter không phải YAML hợp lệ: {e}") from e
    if not isinstance(meta, dict):
        raise FrontmatterError(f"{source_path}: frontmatter phải là mapping key: value")
    return RawDocument(
        source_path=source_path,
        meta=meta,
        body=normalize(text[m.end() :]),
        content_hash=hashlib.sha256(raw).hexdigest(),
    )


def normalize(text: str) -> str:
    """Unicode NFC, bỏ khoảng trắng thừa, bảng Markdown → dòng `Cột: giá trị; ...`."""
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\t", "    ")
    lines = _tables_to_text([line.rstrip() for line in text.split("\n")])
    out = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return out.strip() + "\n"


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _tables_to_text(lines: list[str]) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(lines):
        is_table = lines[i].lstrip().startswith("|") and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1].strip())
        if not is_table:
            out.append(lines[i])
            i += 1
            continue
        header = _cells(lines[i])
        i += 2
        while i < len(lines) and lines[i].lstrip().startswith("|"):
            row = _cells(lines[i])
            out.append("- " + "; ".join(f"{h}: {v}" for h, v in zip(header, row, strict=False) if v))
            i += 1
    return out
