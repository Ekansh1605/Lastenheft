"""
Typed state for the Lastenheft LangGraph.

Every node receives this dict, mutates a subset of fields, and returns
the updated state. Keeping it explicit makes the graph's data flow legible
and makes adding new fields obvious.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, Literal, TypedDict


SovereigntyMode = Literal["local-only", "hybrid", "api-only"]
"""How the LLM router should pick a provider.

- local-only: never call API LLMs; use Qwen3 4B for everything.
- hybrid:     start with local; escalate to API only if validator says reasoning is hard.
- api-only:   skip local; always use the API LLM. For benchmarking, not for production demos.
"""


class Citation(TypedDict):
    """A page that supports (or contradicts) the answer."""
    page_id: str
    document_id: str
    filename: str
    page_number: int
    score: float                 # reranker score, higher = more relevant
    snippet: str                 # short excerpt from extracted_text for the UI tooltip


class TraceEvent(TypedDict):
    """One step of the agent's reasoning trace.
    Surfaced in Langfuse + the SSE stream to the UI."""
    step: str                    # planner | retriever | validator | synthesizer | llm_call
    detail: str                  # human-readable one-liner
    payload: dict[str, Any]      # structured details (counts, scores, provider, etc.)
    latency_ms: int


class AgentState(TypedDict, total=False):
    # ---------- inputs ----------
    query: str
    sovereignty_mode: SovereigntyMode
    session_id: str
    tenant_id: str

    # ---------- planner outputs ----------
    sub_queries: list[str]
    complexity_score: float       # 0..1, used by validator to decide escalation
    plan_rationale: str           # human-readable explanation of decomposition

    # ---------- retriever outputs ----------
    candidate_page_ids: list[str]   # top-N after ColPali ANN, before rerank
    retrieved: list[Citation]       # top-K after LoRA reranker

    # ---------- validator outputs ----------
    coverage_confidence: float    # 0..1, are retrieved pages likely to contain the answer?
    needs_escalation: bool        # if hybrid mode, switch to API LLM
    validation_notes: str

    # ---------- synthesizer outputs ----------
    answer: str
    llm_provider: str             # anthropic | openai | ollama-local
    llm_model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float

    # ---------- aggregate ----------
    # `add` is the LangGraph reducer that concatenates lists across nodes so
    # each TraceEvent emitted by a node appends instead of overwriting.
    trace: Annotated[list[TraceEvent], add]
    total_latency_ms: int
    error: str
