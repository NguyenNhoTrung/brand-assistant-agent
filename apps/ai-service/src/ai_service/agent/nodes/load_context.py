from ai_service.agent.state import AgentState


async def load_context(state: AgentState) -> dict:
    question = state["messages"][-1].content
    # reset field theo lượt (checkpoint mang giá trị lượt trước sang)
    return {"question": question, "evidence": [], "draft_md": None, "final": {}}
