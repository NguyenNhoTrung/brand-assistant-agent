import json

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from ai_service.agent.nodes._common import NOSTREAM, emit, is_artifact, sources_block, started, system_prompt, text_of
from ai_service.agent.nodes.generate_answer import question_block
from ai_service.agent.nodes.generate_artifact import normalize_artifact, require_skill
from ai_service.agent.prompts import load_prompt
from ai_service.agent.state import AgentState
from ai_service.llm.client import chat, structured


def issues_text(state: AgentState) -> str:
    issues = (state.get("verification") or {}).get("issues", [])
    return "\n".join(
        f"- [{i['kind']}{' ' + i['rule_id'] if i.get('rule_id') else ''} · {i.get('severity', 'block')}] "
        f'"{i["excerpt"]}" → {i["fix_hint"]}'
        for i in issues
    )


async def revise(state: AgentState) -> dict:
    started("revise", "Đang chỉnh sửa theo kết quả kiểm tra")
    n = state.get("revision_count", 0) + 1
    sources = sources_block(state["evidence"])
    if is_artifact(state):
        skill = require_skill(state)
        prompt = load_prompt("revise").render(
            issues=issues_text(state), draft=json.dumps(state.get("artifact"), ensure_ascii=False), sources=sources
        )
        msgs = [SystemMessage(system_prompt()), HumanMessage(f"{prompt}\n\nOriginal request: {state['question']}")]
        out = await structured("chat-strong", skill.schema).ainvoke(msgs, config=NOSTREAM)
        assert isinstance(out, BaseModel)
        return {"artifact": normalize_artifact(out.model_dump(mode="json")), "revision_count": n}

    emit("answer.revised", {"reason": issues_text(state), "revision": n})  # UI thay bản nháp bằng bản sửa
    prompt = load_prompt("revise").render(issues=issues_text(state), draft=state.get("draft_md") or "", sources=sources)
    msgs = [SystemMessage(system_prompt()), HumanMessage(f"{prompt}\n\n{question_block(state)}")]
    msg = await chat("chat-default", streaming=True).ainvoke(msgs)
    return {"draft_md": text_of(msg).strip(), "revision_count": n}
