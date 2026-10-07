from typing import Protocol

from ai_service.agent.nodes._common import emit, intent, is_artifact, started
from ai_service.agent.state import AgentState
from ai_service.rag.context_builder import CONTEXT_BUDGET_TOKENS, build_context
from ai_service.rag.retriever import RetrievalQuery, RetrievalResult
from ai_service.skills.registry import get_skill

QA_K = 8
ARTIFACT_K = 14  # nhiều section (product, audience, voice, rules, learnings) → nhiều chunk hơn


class SearchBackend(Protocol):
    async def search_many(self, queries: list[RetrievalQuery], k: int = ...) -> RetrievalResult: ...


def make_retrieve(backend: SearchBackend):
    """Retriever được inject lúc build graph → node không biết Redis/Qdrant được tạo ra sao."""

    async def retrieve(state: AgentState) -> dict:
        started("retrieve", "Đang tìm trong knowledge base")
        queries = [
            RetrievalQuery(text=q["text"], text_en=q.get("text_en") or None, doc_types=q.get("doc_types") or None)
            for q in state.get("queries") or [{"text": state["question"]}]
        ]
        skill = get_skill(intent(state)) if is_artifact(state) else None
        result = await backend.search_many(queries, k=ARTIFACT_K if skill else QA_K)
        pack = build_context(
            result.chunks,
            budget_tokens=skill.max_context_tokens if skill else CONTEXT_BUDGET_TOKENS,
            required_doc_types=skill.doc_types if skill else None,
        )
        evidence = [e.as_dict() for e in pack.evidence]
        emit(
            "retrieval.sources",
            [{k: e[k] for k in ("sid", "chunk_id", "title", "section", "doc_type")} for e in evidence],
        )
        return {
            "evidence": evidence,
            "max_cosine": result.max_cosine,
            "retrieval_attempts": state.get("retrieval_attempts", 0) + 1,
        }

    return retrieve
