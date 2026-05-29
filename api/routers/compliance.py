"""Compliance + audit endpoints. Surfaces AI Act risk classifications and audit log."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query
from pydantic import BaseModel

from agents.audit import audit_log
from ml.ingest.store import get_pool

log = logging.getLogger("lastenheft.api.compliance")

router = APIRouter(prefix="/compliance", tags=["compliance"])


class RiskClassification(BaseModel):
    component: str
    category: str
    article_refs: list[str]
    rationale: str
    mitigations: list[str]


@router.get("/risk-classifications", response_model=list[RiskClassification])
async def list_risk_classifications() -> list[RiskClassification]:
    """Read live from the risk_classifications table (seeded on first DB init)."""
    try:
        with get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT component, category, article_refs, rationale, mitigations "
                "FROM risk_classifications ORDER BY component"
            )
            return [
                RiskClassification(
                    component=row[0], category=row[1],
                    article_refs=list(row[2] or []),
                    rationale=row[3] or "",
                    mitigations=list(row[4] or []),
                )
                for row in cur.fetchall()
            ]
    except Exception as e:  # noqa: BLE001 — fall back to defaults if DB unreachable
        log.warning("failed to read risk_classifications: %s", e)
        return []


@router.get("/audit-log")
async def get_audit_log(limit: int = Query(100, ge=1, le=500)) -> dict[str, object]:
    """Flat audit_events log for the compliance dashboard."""
    events = audit_log(limit=limit)
    # Normalize timestamps to ISO strings for JSON serialization
    for e in events:
        e["created_at"] = str(e["created_at"])
    return {"events": events, "total": len(events)}
