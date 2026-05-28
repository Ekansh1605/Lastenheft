"""Document ingestion endpoint — stub for Day 1; wires into ml/ingest pipeline."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestResponse(BaseModel):
    document_id: str
    page_count: int
    status: str


@router.post("/upload", response_model=IngestResponse)
async def upload_document(file: UploadFile) -> IngestResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")
    # TODO Day 1 (later in session): wire ml/ingest pipeline
    raise HTTPException(status_code=501, detail="Ingest pipeline not yet wired (Day 1 in progress)")
