"""Khung graph: load_context → retrieve → generate_answer → finalize.

TODO(P0) theo ARCHITECTURE_DEMO.md §9: route, plan_retrieval, grade_evidence, generate_artifact,
verify, revise, abstain, respond_direct + edges.py.
"""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ai_service.agent.context import RunContext
from ai_service.agent.nodes.finalize import finalize
from ai_service.agent.nodes.generate_answer import generate_answer
from ai_service.agent.nodes.load_context import load_context
from ai_service.agent.nodes.retrieve import retrieve
from ai_service.agent.state import AgentState

STREAMABLE_NODES = {"generate_answer", "revise"}

Graph = CompiledStateGraph[AgentState, RunContext, AgentState, AgentState]


def build_graph(checkpointer: BaseCheckpointSaver | None = None) -> Graph:
    g = StateGraph(AgentState, context_schema=RunContext)
    g.add_node("load_context", load_context)
    g.add_node("retrieve", retrieve)
    g.add_node("generate_answer", generate_answer)
    g.add_node("finalize", finalize)

    g.add_edge(START, "load_context")
    g.add_edge("load_context", "retrieve")
    g.add_edge("retrieve", "generate_answer")
    g.add_edge("generate_answer", "finalize")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer)
