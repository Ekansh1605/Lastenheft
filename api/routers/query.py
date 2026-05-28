"""Query endpoint — multi-agent retrieval + generation. Stub for Day 1, fleshed out Day 3."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/query", tags=["query"])


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=2)
    sovereignty_mode: str = Field("hybrid", pattern="^(local-only|hybrid|api-only)$")
    session_id: str | None = None


class Citation(BaseModel):
    document_id: str
    page_number: int
    score: float
    bbox: list[float] | None = None


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    llm_provider: str
    llm_model: str
    confidence: float
    latency_ms: int
    cost_usd: float
    session_id: str


@router.post("", response_model=QueryResponse)
async def run_query(req: QueryRequest) -> QueryResponse:
    # TODO Day 3: LangGraph planner → retriever → validator → synthesizer
    raise HTTPException(status_code=501, detail="Query pipeline scheduled for Day 3")
