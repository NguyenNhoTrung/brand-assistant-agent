import pytest

from ai_service.agent.graph import Graph

from .conftest import ask

pytestmark = [pytest.mark.llm, pytest.mark.infra]


async def test_second_turn_resolves_pronoun_from_first(graph: Graph) -> None:
    first = await ask(graph, "Tell me about the Vitamin C Serum", thread="mem-1")
    assert first["status"] in {"answered", "partial"}
    second = await ask(graph, "thế còn giá của nó?", thread="mem-1")
    assert second["status"] in {"answered", "partial"}
    assert "42" in second["answer_md"]
    assert "products/vitamin-c-serum.md" in {c["source_path"] for c in second["citations"]}
