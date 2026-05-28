"""Compliance + audit endpoints. Surfaces AI Act risk classifications and audit log."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/compliance", tags=["compliance"])


class RiskClassification(BaseModel):
    component: str
    category: str
    article_refs: list[str]
    rationale: str
    mitigations: list[str]


@router.get("/risk-classifications", response_model=list[RiskClassification])
async def list_risk_classifications() -> list[RiskClassification]:
    # TODO Day 4: read from `risk_classifications` table; for now return seed values
    return [
        RiskClassification(
            component="system-overall",
            category="limited",
            article_refs=["Article 6", "Article 13", "Article 50"],
            rationale=(
                "Document Q&A over industrial technical documentation. Not a safety "
                "component of machinery (Annex I). Not making consequential automated "
                "decisions about persons (Annex III). Transparency obligation applies "
                "under Art. 50 since LLM-generated content is exposed to humans."
            ),
            mitigations=[
                "Citation overlay on every answer",
                "Provider disclosure per answer",
                "Audit log per Art. 13",
                "Human-in-the-loop validation step",
            ],
        ),
    ]


@router.get("/audit-log")
async def audit_log_summary() -> dict[str, object]:
    # TODO Day 4: query audit_events with filters
    return {"events": [], "total": 0, "note": "Audit log surfacing scheduled for Day 4"}
