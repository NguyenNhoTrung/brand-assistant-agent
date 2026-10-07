import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from ai_service.agent.nodes._common import NOSTREAM, intent, sources_block, started, system_prompt
from ai_service.agent.nodes.generate_answer import coverage_note
from ai_service.agent.prompts import load_prompt
from ai_service.agent.state import AgentState
from ai_service.llm.client import structured
from ai_service.skills.registry import Skill, get_skill

_MARKERS = re.compile(r"\s*\[\s*(S\d+(?:\s*[,;]\s*S\d+)*)\s*\]")
_SID = re.compile(r"S\d+")


def normalize_artifact(value: Any) -> Any:
    """Model hay chèn `[S#]` ngay trong text: chuyển vào `source_ids` (CitedText) / bỏ khỏi chuỗi thường —
    citation của artifact chỉ đi qua `source_ids` để verify kiểm được và render không lặp marker."""
    if isinstance(value, dict):
        out = {k: normalize_artifact(v) for k, v in value.items()}
        if isinstance(value.get("text"), str) and isinstance(value.get("source_ids"), list):
            inline = [sid for m in _MARKERS.finditer(value["text"]) for sid in _SID.findall(m.group(1))]
            out["source_ids"] = list(dict.fromkeys([*value["source_ids"], *inline]))
        return out
    if isinstance(value, list):
        return [normalize_artifact(v) for v in value]
    if isinstance(value, str):
        return _MARKERS.sub("", value).strip().strip('"“”').strip()
    return value


def require_skill(state: AgentState) -> Skill:
    skill = get_skill(intent(state))
    if skill is None:
        raise RuntimeError(f"Không có skill cho intent {intent(state)!r}")
    return skill


async def generate_artifact(state: AgentState) -> dict:
    """Artifact KHÔNG stream token (§7.4) — chỉ gửi sau khi verify."""
    started("generate_artifact", "Đang soạn artifact")
    skill = require_skill(state)
    prompt = load_prompt("artifact").render(
        skill=skill.instructions,
        publishable=", ".join(sorted(skill.publishable_fields)),
        coverage=coverage_note(state),
        sources=sources_block(state["evidence"]),
    )
    msgs = [SystemMessage(system_prompt()), HumanMessage(f"{prompt}\n\nRequest: {state['question']}")]
    out = await structured("chat-strong", skill.schema).ainvoke(msgs, config=NOSTREAM)
    assert isinstance(out, BaseModel)
    return {"artifact": normalize_artifact(out.model_dump(mode="json"))}
