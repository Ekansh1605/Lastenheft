"""Query endpoint — wires the LangGraph multi-agent into HTTP, with auditing.

POST /query             synchronous, returns full final state
POST /query/stream      SSE events as each agent node fires
GET  /query/history     list past queries for a session (sidebar)
GET  /query/{query_id}  fetch one past query's state for replay in the UI
DEL  /query/{query_id}  GDPR Article 17 — delete a past query + its audit events
DEL  /session/{session} wipe an entire session (right to erasure)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import time
import uuid

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from agents.audit import (
    audit_events_for_session,
    delete_query,
    delete_session,
    get_query,
    list_history,
    persist_run,
)
from agents.graph import get_graph
from agents.langfuse_client import log_span, trace as langfuse_trace

log = logging.getLogger("lastenheft.api.query")

# Per-router limiter — used as a decorator below
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/query", tags=["query"])
session_router = APIRouter(prefix="/session", tags=["query"])

AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT_SECONDS", "180"))


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


def _validate_uuid(s: str | None) -> str | None:
    if not s:
        return None
    try:
        uuid.UUID(s)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"invalid UUID: {s}")
    return s


def _build_initial(req: QueryRequest) -> dict:
    sid = _validate_uuid(req.session_id) or str(uuid.uuid4())
    tid = _validate_uuid(req.tenant_id) or "00000000-0000-0000-0000-000000000000"
    return {
        "query": req.query,
        "sovereignty_mode": req.sovereignty_mode,
        "session_id": sid,
        "tenant_id": tid,
        "trace": [],
    }


def _to_response(state: dict, total_ms: int, query_id: str) -> QueryResponse:
    return QueryResponse(
        query_id=query_id,
        user_query=str(state.get("query", "")),
        answer=state.get("answer", "") or "(no answer)",
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


# ---------- POST /query (synchronous, timeboxed) ----------

@router.post("", response_model=QueryResponse)
@limiter.limit(f"{os.getenv('RATE_LIMIT_PER_MINUTE', '10')}/minute")
async def run_query(request: Request, req: QueryRequest) -> QueryResponse:
    graph = get_graph()
    initial = _build_initial(req)
    t0 = time.perf_counter()
    with langfuse_trace(
        name="agent.run",
        session_id=initial["session_id"],
        metadata={"sovereignty_mode": req.sovereignty_mode, "query_preview": req.query[:120]},
    ) as lf:
        try:
            final = await asyncio.wait_for(
                asyncio.to_thread(graph.invoke, initial),
                timeout=AGENT_TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=504,
                detail=f"Agent timed out after {AGENT_TIMEOUT}s. Try a shorter query, switch sovereignty mode, or check that Ollama is reachable.",
            )
        total_ms = int((time.perf_counter() - t0) * 1000)
        # Forward the same trace data that goes into the audit log to Langfuse
        for ev in final.get("trace", []):
            log_span(lf, name=ev["step"], latency_ms=ev.get("latency_ms", 0),
                     output_data=ev.get("detail"), metadata=ev.get("payload"))
    query_id = persist_run(final, total_ms)
    return _to_response(final, total_ms, query_id)


# ---------- POST /query/stream (SSE) ----------

@router.post("/stream")
@limiter.limit(f"{os.getenv('RATE_LIMIT_PER_MINUTE', '10')}/minute")
async def run_query_stream(request: Request, req: QueryRequest):
    """SSE stream of agent steps with timeout + client-disconnect cancellation."""
    graph = get_graph()
    initial = _build_initial(req)

    async def gen():
        t0 = time.perf_counter()
        last_state: dict = dict(initial)

        # Run the graph in a worker thread so we can interleave SSE writes
        # and disconnect checks on the event loop.
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def drive_graph():
            try:
                for chunk in graph.stream(initial, stream_mode="updates"):
                    loop.call_soon_threadsafe(queue.put_nowait, ("chunk", chunk))
            except Exception as e:  # noqa: BLE001
                loop.call_soon_threadsafe(queue.put_nowait, ("error", e))
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

        worker = asyncio.create_task(asyncio.to_thread(drive_graph))
        deadline = loop.time() + AGENT_TIMEOUT

        try:
            while True:
                # Hard timeout
                remaining = deadline - loop.time()
                if remaining <= 0:
                    yield f"event: error\ndata: {json.dumps({'detail': 'agent timed out'})}\n\n"
                    return
                # Client closed the tab?
                if await request.is_disconnected():
                    log.info("client disconnected mid-stream, cancelling agent")
                    return
                try:
                    kind, value = await asyncio.wait_for(queue.get(), timeout=min(5.0, remaining))
                except asyncio.TimeoutError:
                    # Send a comment-keepalive so proxies don't close the connection
                    yield ": keepalive\n\n"
                    continue
                if kind == "chunk":
                    for node_name, update in value.items():
                        last_state.update(update)
                        payload = {
                            "type": "node",
                            "node": node_name,
                            "trace": update.get("trace", []),
                            "partial_answer": update.get("answer"),
                            "citations": update.get("retrieved"),
                        }
                        yield f"data: {json.dumps(payload, default=str, ensure_ascii=False)}\n\n"
                elif kind == "error":
                    yield f"event: error\ndata: {json.dumps({'detail': str(value)})}\n\n"
                    return
                elif kind == "done":
                    break
        finally:
            with contextlib.suppress(Exception):
                worker.cancel()

        total_ms = int((time.perf_counter() - t0) * 1000)
        query_id = persist_run(last_state, total_ms)
        # Forward to Langfuse after persistence so the trace carries the query_id
        with langfuse_trace(
            name="agent.run.stream",
            session_id=last_state.get("session_id"),
            metadata={"sovereignty_mode": req.sovereignty_mode, "query_id": query_id,
                       "query_preview": req.query[:120]},
        ) as lf:
            for ev in last_state.get("trace", []):
                log_span(lf, name=ev["step"], latency_ms=ev.get("latency_ms", 0),
                         output_data=ev.get("detail"), metadata=ev.get("payload"))
        final = _to_response(last_state, total_ms, query_id).model_dump()
        yield f"event: done\ndata: {json.dumps(final, default=str, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


# ---------- GET /query/history ----------

@router.get("/history", response_model=list[HistoryItem])
async def query_history(
    session_id: str = Query(..., description="Browser session ID"),
    limit: int = Query(50, ge=1, le=200),
) -> list[HistoryItem]:
    _validate_uuid(session_id)
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


# ---------- GET /query/{id} (replay with audit trace) ----------

@router.get("/{query_id}")
async def replay_query(query_id: str):
    _validate_uuid(query_id)
    row = get_query(query_id)
    if row is None:
        raise HTTPException(status_code=404, detail="query not found")
    trace = audit_events_for_session(
        row["session_id"], around_query_id=query_id,
    )
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
        "trace": trace,
    }


# ---------- DELETE /query/{id} (GDPR Art. 17) ----------

@router.delete("/{query_id}", status_code=204)
async def erase_query(query_id: str):
    _validate_uuid(query_id)
    if not delete_query(query_id):
        raise HTTPException(status_code=404, detail="query not found")


@session_router.delete("/{session_id}", status_code=204)
async def erase_session(session_id: str):
    _validate_uuid(session_id)
    delete_session(session_id)
