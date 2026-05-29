"""
LangGraph wiring for the Lastenheft Q&A flow.

Linear graph for now: planner -> retriever -> validator -> synthesizer.
The validator's `needs_escalation` flag is consumed by the synthesizer's
LLM router rather than branching the graph itself — keeps the graph
shape simple and the routing decision auditable in one place.

Returning a compiled graph means callers can `.invoke(state)` for the
full result or `.stream(state)` for SSE-friendly node-by-node updates
(used by the Next.js UI later).
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agents.nodes import planner, retriever, synthesizer, validator
from agents.state import AgentState


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("planner", planner)
    g.add_node("retriever", retriever)
    g.add_node("validator", validator)
    g.add_node("synthesizer", synthesizer)

    g.add_edge(START, "planner")
    g.add_edge("planner", "retriever")
    g.add_edge("retriever", "validator")
    g.add_edge("validator", "synthesizer")
    g.add_edge("synthesizer", END)

    return g.compile()


# Module-level singleton — LangGraph compile is cheap but doing it once is cleaner
_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH
