from langgraph.config import get_stream_writer

from ai_service.agent.state import AgentState


async def retrieve(state: AgentState) -> dict:
    write = get_stream_writer()
    write({"type": "node.started", "data": {"node": "retrieve", "label": "Đang tìm trong knowledge base"}})
    # TODO(P0): hybrid retriever (rag/retriever.py) — hiện trả 1 chunk giả để chạy end-to-end
    evidence = [{"sid": "S1", "chunk_id": "demo#0", "title": "Demo source", "section": "", "text": "..."}]
    write(
        {
            "type": "retrieval.sources",
            "data": [{k: e[k] for k in ("sid", "chunk_id", "title")} for e in evidence],
        }
    )
    return {"evidence": evidence}
