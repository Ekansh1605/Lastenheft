"""
Audit persistence for the Lastenheft agent runs.

Every successful agent invocation writes:
    * one row into `query_sessions` (idempotent on session_id)
    * one row into `queries` (the user-visible record — surfaces in sidebar history)
    * N rows into `audit_events` (one per agent node + LLM call,
      per EU AI Act Article 13 transparency obligation)

Kept separate from agents/nodes.py so the agent logic stays a pure dataflow
graph — auditing is a side-effect orchestrated by the API layer right after
graph.invoke() returns.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from ml.ingest.store import get_pool

log = logging.getLogger("lastenheft.audit")


def _ensure_session(cur, session_id: str, tenant_id: str, user_id: str | None) -> None:
    cur.execute(
        """
        INSERT INTO query_sessions (id, tenant_id, user_id)
        VALUES (%s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (session_id, tenant_id, user_id),
    )


def persist_run(state: dict[str, Any], total_latency_ms: int) -> str:
    """Write the audit trail for one completed agent run. Returns the query UUID."""
    session_id = str(state.get("session_id") or uuid.uuid4())
    tenant_id = str(state.get("tenant_id") or "00000000-0000-0000-0000-000000000000")
    user_id = state.get("user_id")
    query_id = str(uuid.uuid4())

    retrieved = state.get("retrieved") or []
    retrieved_summary = [
        {
            "page_id": c.get("page_id"),
            "filename": c.get("filename"),
            "page_number": c.get("page_number"),
            "score": c.get("score"),
        }
        for c in retrieved
    ]

    try:
        with get_pool().connection() as conn, conn.cursor() as cur:
            _ensure_session(cur, session_id, tenant_id, user_id)

            cur.execute(
                """
                INSERT INTO queries (
                    id, session_id, user_query, planner_decomposition,
                    retrieved_pages, final_answer, llm_provider, llm_model,
                    sovereignty_mode, confidence, latency_ms, cost_usd
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    query_id, session_id,
                    state.get("query", ""),
                    json.dumps({
                        "sub_queries": state.get("sub_queries"),
                        "complexity": state.get("complexity_score"),
                        "rationale": state.get("plan_rationale"),
                    }),
                    json.dumps(retrieved_summary),
                    state.get("answer", ""),
                    state.get("llm_provider", "unknown"),
                    state.get("llm_model", "unknown"),
                    state.get("sovereignty_mode", "hybrid"),
                    float(state.get("coverage_confidence", 0.0)),
                    int(total_latency_ms),
                    float(state.get("cost_usd", 0.0)),
                ),
            )

            # One audit_events row per TraceEvent (Article 13 transparency log)
            for ev in state.get("trace") or []:
                payload = dict(ev.get("payload") or {})
                cur.execute(
                    """
                    INSERT INTO audit_events (
                        tenant_id, user_id, session_id, event_type, payload,
                        llm_provider, llm_model, token_input, token_output,
                        cost_usd, latency_ms
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        tenant_id, user_id, session_id, ev.get("step", "unknown"),
                        json.dumps({"detail": ev.get("detail"), **payload}),
                        payload.get("provider"),
                        payload.get("model"),
                        int(payload.get("tokens_in") or 0) or None,
                        int(payload.get("tokens_out") or 0) or None,
                        float(payload.get("cost_usd") or 0.0) or None,
                        int(ev.get("latency_ms") or 0),
                    ),
                )
            conn.commit()
    except Exception as e:  # noqa: BLE001 — auditing must never break the user response
        log.warning("audit persist failed: %s", e)

    return query_id


# ---------- read side ----------

def list_history(session_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Sidebar list — query previews for one browser session, newest first."""
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id::text, user_query, llm_provider, llm_model, sovereignty_mode,
                   cost_usd, latency_ms, created_at
            FROM queries
            WHERE session_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (session_id, limit),
        )
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def get_query(query_id: str) -> dict[str, Any] | None:
    """Full row for a past query so the UI can re-render it."""
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id::text, session_id::text, user_query, planner_decomposition,
                   retrieved_pages, final_answer, llm_provider, llm_model,
                   sovereignty_mode, confidence, latency_ms, cost_usd, created_at
            FROM queries WHERE id::text = %s
            """,
            (query_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        cols = [c.name for c in cur.description]
        return dict(zip(cols, row, strict=True))


def audit_log(limit: int = 200) -> list[dict[str, Any]]:
    """Compliance dashboard data — flat list of audit_events, newest first."""
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id::text, session_id::text, event_type, payload,
                   llm_provider, llm_model, token_input, token_output,
                   cost_usd, latency_ms, created_at
            FROM audit_events
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
