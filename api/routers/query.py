"""Query endpoint — wires the LangGraph multi-agent into HTTP.

POST /query returns the full final state (synchronous).
POST /query/stream returns SSE events as each agent node fires (used by the
Next.js UI for the live agent-trajectory viewer).
"""

from __future__ import annotations

import json
import logging
import time
import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agents.graph import get_graph

log = logging.getLogger("lastenheft.api.query")

router = APIRouter(prefix="/query", tags=["query"])


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000)
    sovereignty_mode: str = Field("hybrid", pattern="^(local-only|hybrid|api-only)$")
    session_id: str | None = None
    tenant_id: str | None = None


class CitationOut(BaseModel):
    page_id: str
    document_id: str
    filename: str
    page_number: int
    score: float
    snippet: str


class TraceEventOut(BaseModel):
    step: str
    detail: str
    latency_ms: int
    payload: dict


class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationOut]
    llm_provider: str
    llm_model: str
    confidence: float
    sovereignty_mode: str
    needs_escalation: bool
    input_tokens: int
    output_tokens: int
    cost_usd: float
    total_latency_ms: int
    session_id: str
    trace: list[TraceEventOut]


def _build_initial(req: QueryRequest) -> dict:
    return {
        "query": req.query,
        "sovereignty_mode": req.sovereignty_mode,
        "session_id": req.session_id or str(uuid.uuid4()),
        "tenant_id": req.tenant_id or "00000000-0000-0000-0000-000000000000",
        "trace": [],
    }


def _to_response(state: dict, total_ms: int) -> QueryResponse:
    return QueryResponse(
        answer=state.get("answer", ""),
        citations=[CitationOut(**c) for c in state.get("retrieved", [])],
        llm_provider=state.get("llm_provider", ""),
        llm_model=state.get("llm_model", ""),
        confidence=state.get("coverage_confidence", 0.0),
        sovereignty_mode=state.get("sovereignty_mode", "hybrid"),
        needs_escalation=bool(state.get("needs_escalation", False)),
        input_tokens=int(state.get("input_tokens", 0)),
        output_tokens=int(state.get("output_tokens", 0)),
        cost_usd=float(state.get("cost_usd", 0.0)),
        total_latency_ms=total_ms,
        session_id=str(state.get("session_id", "")),
        trace=[TraceEventOut(**e) for e in state.get("trace", [])],
    )


@router.post("", response_model=QueryResponse)
async def run_query(req: QueryRequest) -> QueryResponse:
    graph = get_graph()
    initial = _build_initial(req)
    t0 = time.perf_counter()
    final = graph.invoke(initial)
    total_ms = int((time.perf_counter() - t0) * 1000)
    return _to_response(final, total_ms)


@router.post("/stream")
async def run_query_stream(req: QueryRequest):
    """Server-Sent Events stream of agent steps. Each event = one node finishing."""
    graph = get_graph()
    initial = _build_initial(req)

    def gen():
        t0 = time.perf_counter()
        last_state: dict = dict(initial)
        for chunk in graph.stream(initial, stream_mode="updates"):
            # chunk is {"node_name": <state-update-dict>}
            for node_name, update in chunk.items():
                last_state.update(update)
                payload = {
                    "type": "node",
                    "node": node_name,
                    "trace": update.get("trace", []),
                    "partial_answer": update.get("answer"),
                    "citations": update.get("retrieved"),
                }
                yield f"data: {json.dumps(payload, default=str, ensure_ascii=False)}\n\n"
        total_ms = int((time.perf_counter() - t0) * 1000)
        final = _to_response(last_state, total_ms).model_dump()
        yield f"event: done\ndata: {json.dumps(final, default=str, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
