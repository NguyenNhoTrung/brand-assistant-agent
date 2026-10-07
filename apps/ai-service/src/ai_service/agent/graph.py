"""Graph đủ 12 node (§9.2–9.3): route → plan → retrieve → grade → generate → verify → revise → finalize,
cộng respond_direct và abstain. Vòng lặp có giới hạn: retrieve ≤ 2 lần, revise ≤ 2 lần (edges.py)."""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from ai_service.agent.context import RunContext
from ai_service.agent.edges import after_grade, after_route, after_verify
from ai_service.agent.errors import is_transient
from ai_service.agent.nodes.abstain import abstain
from ai_service.agent.nodes.finalize import finalize
from ai_service.agent.nodes.generate_answer import generate_answer
from ai_service.agent.nodes.generate_artifact import generate_artifact
from ai_service.agent.nodes.grade_evidence import grade_evidence
from ai_service.agent.nodes.load_context import load_context
from ai_service.agent.nodes.plan_retrieval import plan_retrieval
from ai_service.agent.nodes.respond_direct import respond_direct
from ai_service.agent.nodes.retrieve import SearchBackend, make_retrieve
from ai_service.agent.nodes.revise import revise
from ai_service.agent.nodes.route import route
from ai_service.agent.nodes.verify import verify
from ai_service.agent.state import AgentState

STREAMABLE_NODES = {"generate_answer", "revise"}  # artifact gọi LLM với tag "nostream" → không lộ token

Graph = CompiledStateGraph[AgentState, RunContext, AgentState, AgentState]


def build_graph(checkpointer: BaseCheckpointSaver | None = None, *, retriever: SearchBackend) -> Graph:
    g = StateGraph(AgentState, context_schema=RunContext)
    infra_retry = RetryPolicy(max_attempts=3, retry_on=is_transient)

    g.add_node("load_context", load_context)
    g.add_node("route", route)
    g.add_node("respond_direct", respond_direct)
    g.add_node("plan_retrieval", plan_retrieval)
    g.add_node("retrieve", make_retrieve(retriever), retry_policy=infra_retry)
    g.add_node("grade_evidence", grade_evidence)
    g.add_node("generate_answer", generate_answer)
    g.add_node("generate_artifact", generate_artifact)
    g.add_node("verify", verify)
    g.add_node("revise", revise)
    g.add_node("abstain", abstain)
    g.add_node("finalize", finalize)

    g.add_edge(START, "load_context")
    g.add_edge("load_context", "route")
    g.add_conditional_edges("route", after_route, ["respond_direct", "plan_retrieval"])
    g.add_edge("plan_retrieval", "retrieve")
    g.add_edge("retrieve", "grade_evidence")
    g.add_conditional_edges(
        "grade_evidence", after_grade, ["retrieve", "abstain", "generate_answer", "generate_artifact"]
    )
    g.add_edge("generate_answer", "verify")
    g.add_edge("generate_artifact", "verify")
    g.add_conditional_edges("verify", after_verify, ["revise", "finalize"])
    g.add_edge("revise", "verify")
    g.add_edge("abstain", "finalize")
    g.add_edge("respond_direct", "finalize")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer)
