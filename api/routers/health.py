"""Health + readiness endpoints. Used by Docker, Vercel, and uptime monitors."""

from __future__ import annotations

import os

import httpx
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readiness() -> dict[str, object]:
    """Reports readiness of each subsystem so Docker compose knows when we're live."""
    checks: dict[str, str] = {}

    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{ollama_host}/api/tags")
            checks["ollama"] = "ok" if r.status_code == 200 else f"error:{r.status_code}"
    except Exception as e:  # noqa: BLE001 — surface all errors as not-ready
        checks["ollama"] = f"unreachable:{type(e).__name__}"

    return {"status": "ok" if all(v == "ok" for v in checks.values()) else "degraded",
            "checks": checks}
