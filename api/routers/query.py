"""Query endpoint — wires the LangGraph multi-agent into HTTP, with auditing.

POST /query             synchronous, returns full final state
POST /query/stream      SSE events as each agent node fires
GET  /query/history     list past queries for a session (sidebar)
GET  /query/{query_id}  fetch one past query's state for replay in the UI
"""

from __future__ import annotations

import json
import logging
import time
import uuid

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agents.audit import get_query, list_history, persist_run
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
    query_id: str
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
    user_query: str


class HistoryItem(BaseModel):
    id: str
    user_query: str
    llm_provider: str
    llm_model: str
    sovereignty_mode: str
    cost_usd: float
    latency_ms: int
    created_at: str


def _build_initial(req: QueryRequest) -> dict:
    return {
        "query": req.query,
        "sovereignty_mode": req.sovereignty_mode,
        "session_id": req.session_id or str(uuid.uuid4()),
        "tenant_id": req.tenant_id or "00000000-0000-0000-0000-000000000000",
        "trace": [],
    }


def _to_response(state: dict, total_ms: int, query_id: str) -> QueryResponse:
    return QueryResponse(
        query_id=query_id,
        user_query=str(state.get("query", "")),
        answer=state.get("answer", ""),
        citations=[CitationOut(**c) for c in state.get("retrieved", [])],
        llm_provider=state.get("llm_provider", ""),
        llm_model=state.get("llm_model", ""),
        confidence=float(state.get("coverage_confidence", 0.0)),
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
    query_id = persist_run(final, total_ms)
    return _to_response(final, total_ms, query_id)


@router.post("/stream")
async def run_query_stream(req: QueryRequest):
    """SSE stream of agent steps. Each event = one node finishing. Final 'done' event
    fires after auditing completes and carries the persisted query_id."""
    graph = get_graph()
    initial = _build_initial(req)

    def gen():
        t0 = time.perf_counter()
        last_state: dict = dict(initial)
        for chunk in graph.stream(initial, stream_mode="updates"):
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
        query_id = persist_run(last_state, total_ms)
        final = _to_response(last_state, total_ms, query_id).model_dump()
        yield f"event: done\ndata: {json.dumps(final, default=str, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/history", response_model=list[HistoryItem])
async def query_history(
    session_id: str = Query(..., description="Browser session ID"),
    limit: int = Query(50, ge=1, le=200),
) -> list[HistoryItem]:
    rows = list_history(session_id, limit=limit)
    return [
        HistoryItem(
            id=r["id"], user_query=r["user_query"],
            llm_provider=r["llm_provider"], llm_model=r["llm_model"],
            sovereignty_mode=r["sovereignty_mode"],
            cost_usd=float(r["cost_usd"] or 0.0),
            latency_ms=int(r["latency_ms"] or 0),
            created_at=str(r["created_at"]),
        )
        for r in rows
    ]


@router.get("/{query_id}")
async def replay_query(query_id: str):
    row = get_query(query_id)
    if row is None:
        raise HTTPException(status_code=404, detail="query not found")
    # Normalize JSONB -> Python lists/dicts so the UI can render directly
    return {
        "query_id": row["id"],
        "session_id": row["session_id"],
        "user_query": row["user_query"],
        "planner": row["planner_decomposition"],
        "retrieved_pages": row["retrieved_pages"],
        "answer": row["final_answer"],
        "llm_provider": row["llm_provider"],
        "llm_model": row["llm_model"],
        "sovereignty_mode": row["sovereignty_mode"],
        "confidence": float(row["confidence"] or 0.0),
        "latency_ms": int(row["latency_ms"] or 0),
        "cost_usd": float(row["cost_usd"] or 0.0),
        "created_at": str(row["created_at"]),
    }
