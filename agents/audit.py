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


def audit_log(limit: int = 200, offset: int = 0) -> dict[str, Any]:
    """Compliance dashboard data — paginated audit_events, newest first.

    Returns {events, total} for the UI's pagination footer.
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM audit_events")
        total = int(cur.fetchone()[0])
        cur.execute(
            """
            SELECT id::text, session_id::text, event_type, payload,
                   llm_provider, llm_model, token_input, token_output,
                   cost_usd, latency_ms, created_at
            FROM audit_events
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        cols = [c.name for c in cur.description]
        events = [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
    return {"events": events, "total": total}


def audit_events_for_session(session_id: str, around_query_id: str | None = None,
                             limit: int = 20) -> list[dict[str, Any]]:
    """Return the most recent N audit_events for a session, filtered down to the
    burst surrounding a specific query if `around_query_id` is provided.

    This is used by the /query/{id} replay endpoint so the UI can show the
    full agent trace for a past query, not just the summary."""
    with get_pool().connection() as conn, conn.cursor() as cur:
        # We rely on per-run audit_events landing in tight time windows; pull
        # the most recent N for this session as a reasonable approximation
        # when we don't yet have a foreign key from audit_events -> queries.
        cur.execute(
            """
            SELECT event_type, payload, latency_ms
            FROM audit_events
            WHERE session_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (session_id, limit),
        )
        rows = cur.fetchall()
    # Reverse to chronological for the UI timeline
    out: list[dict[str, Any]] = []
    for row in reversed(rows):
        event_type, payload, latency_ms = row
        payload = payload or {}
        out.append({
            "step": event_type,
            "detail": payload.get("detail", ""),
            "latency_ms": int(latency_ms or 0),
            "payload": {k: v for k, v in payload.items() if k != "detail"},
        })
    return out


def delete_query(query_id: str) -> bool:
    """GDPR Art. 17 right-to-erasure on a single query.
    Returns True if a row was actually deleted."""
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT session_id::text FROM queries WHERE id::text = %s", (query_id,))
        row = cur.fetchone()
        if not row:
            return False
        # We also remove the audit_events that this query produced.
        # Since audit_events don't have a query_id FK, we delete by session+time-window:
        # the safe approach for now is to just delete this query and leave audit
        # events (they're aggregate observability). Full FK would be a Day 5 task.
        cur.execute("DELETE FROM queries WHERE id::text = %s", (query_id,))
        conn.commit()
    return True


def delete_session(session_id: str) -> int:
    """Wipe everything for one browser session (queries + their audit events)."""
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM audit_events WHERE session_id = %s", (session_id,))
        n_audit = cur.rowcount
        cur.execute("DELETE FROM queries WHERE session_id = %s", (session_id,))
        n_queries = cur.rowcount
        cur.execute("DELETE FROM query_sessions WHERE id = %s", (session_id,))
        conn.commit()
    log.info("deleted session %s: %d queries + %d audit_events",
             session_id, n_queries, n_audit)
    return n_queries
