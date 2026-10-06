import re

from ai_service.agent.state import AgentState
from shared.contracts import Citation, FinalPayload


async def finalize(state: AgentState) -> dict:
    answer = state.get("draft_md") or ""
    by_sid = {e["sid"]: e for e in state.get("evidence", [])}
    used = list(dict.fromkeys(re.findall(r"\[(S\d+)\]", answer)))
    citations = [
        Citation(n=i + 1, sid=s, chunk_id=by_sid[s]["chunk_id"], title=by_sid[s]["title"])
        for i, s in enumerate(used)
        if s in by_sid
    ]
    final = FinalPayload(status="answered", answer_md=answer, citations=citations, confidence="medium")
    return {"final": final.model_dump(mode="json")}
