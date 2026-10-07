"""Prompt là file `*.md` cạnh module này, dòng đầu `<!-- version: N -->` → trace ghi `prompt_version` (§9.8).

Biến trong prompt viết `{{name}}`; `render()` thay thế, biến thiếu → lỗi ngay (không lặng lẽ gửi prompt hỏng).
"""

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

_DIR = Path(__file__).parent
_VERSION = re.compile(r"^<!--\s*version:\s*(\S+)\s*-->\s*\n")
_VAR = re.compile(r"\{\{\s*(\w+)\s*\}\}")


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    text: str

    def render(self, **values: str) -> str:
        def sub(m: re.Match[str]) -> str:
            if m.group(1) not in values:
                raise KeyError(f"prompt {self.name}: thiếu biến {m.group(1)!r}")
            return values[m.group(1)]

        return _VAR.sub(sub, self.text)


@cache
def load_prompt(name: str) -> Prompt:
    raw = (_DIR / f"{name}.md").read_text(encoding="utf-8")
    m = _VERSION.match(raw)
    if not m:
        raise ValueError(f"prompts/{name}.md thiếu dòng đầu <!-- version: N -->")
    return Prompt(name=name, version=m.group(1), text=raw[m.end() :].strip())
