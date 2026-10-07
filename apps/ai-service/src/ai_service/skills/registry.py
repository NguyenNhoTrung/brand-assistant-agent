"""Skills pattern (§9.7): mỗi folder con có `SKILL.md` là một skill — thêm loại output = thêm folder.

Folder cần: `SKILL.md`, `schema.py` (biến `SCHEMA` = Pydantic model có `PUBLISHABLE_FIELDS`),
`retrieval_plan.yaml`, `render.md.j2`, `rubric.yaml` (dùng ở eval).
"""

import importlib
from collections import defaultdict
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import jinja2
import yaml
from pydantic import BaseModel

_DIR = Path(__file__).parent
_DEFAULT_SLOTS = {"product": "our product", "category": "skincare", "channel": "social video"}


@dataclass(frozen=True)
class SectionQuery:
    name: str
    query: str
    doc_types: tuple[str, ...]


@dataclass(frozen=True)
class Skill:
    name: str
    instructions: str  # SKILL.md → nạp vào prompt sinh artifact
    schema: type[BaseModel]
    sections: tuple[SectionQuery, ...]
    max_context_tokens: int
    template: jinja2.Template
    rubric_path: Path

    @property
    def publishable_fields(self) -> set[str]:
        return set(getattr(self.schema, "PUBLISHABLE_FIELDS", set()))

    @property
    def required_phrase_field(self) -> str | None:
        return getattr(self.schema, "REQUIRED_PHRASE_FIELD", None)

    @property
    def doc_types(self) -> list[str]:
        return list(dict.fromkeys(dt for s in self.sections for dt in s.doc_types))

    def queries(self, slots: dict[str, str | None]) -> list[tuple[str, tuple[str, ...]]]:
        """Điền `{product}`/`{category}`/`{channel}` vào retrieval plan; slot thiếu → giá trị chung."""
        values: defaultdict[str, str] = defaultdict(str, _DEFAULT_SLOTS)
        values.update({k: v for k, v in slots.items() if v})
        return [(s.query.format_map(values), s.doc_types) for s in self.sections]

    def render(self, artifact: dict[str, Any]) -> str:
        return self.template.render(a=artifact).strip() + "\n"


def _load(folder: Path) -> Skill:
    module = importlib.import_module(f"{__package__}.{folder.name}.schema")
    plan = yaml.safe_load((folder / "retrieval_plan.yaml").read_text(encoding="utf-8"))
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(folder), autoescape=False, trim_blocks=True, lstrip_blocks=True
    )
    return Skill(
        name=folder.name,
        instructions=(folder / "SKILL.md").read_text(encoding="utf-8"),
        schema=module.SCHEMA,
        sections=tuple(
            SectionQuery(name=k, query=v["query"], doc_types=tuple(v.get("doc_types") or ()))
            for k, v in plan["sections"].items()
        ),
        max_context_tokens=int(plan.get("max_context_tokens", 6000)),
        template=env.get_template("render.md.j2"),
        rubric_path=folder / "rubric.yaml",
    )


@cache
def registry() -> dict[str, Skill]:
    return {d.name: _load(d) for d in sorted(_DIR.iterdir()) if (d / "SKILL.md").is_file()}


def get_skill(name: str) -> Skill | None:
    return registry().get(name)
