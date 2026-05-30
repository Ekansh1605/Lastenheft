"""FastAPI entrypoint for the Lastenheft ML orchestration layer."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from api.routers import compliance, health, query
from api.routers.query import session_router

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
)
log = logging.getLogger("lastenheft.api")


# ---------- rate limiter ----------
# Per-IP throttle to keep a shared demo URL from being scraped to drain API costs.
_RPM = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
limiter = Limiter(key_func=get_remote_address, default_limits=[f"{_RPM}/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Lastenheft API starting (env=%s allow_api_llm=%s rate=%s/min)",
             os.getenv("APP_ENV", "development"),
             os.getenv("ALLOW_API_LLM", "true"),
             _RPM)
    yield
    log.info("Lastenheft API shutting down")


app = FastAPI(
    title="Lastenheft API",
    version="0.1.0",
    description="Sovereign multimodal document intelligence for industrial manufacturing.",
    lifespan=lifespan,
)

# Make limiter available to routers via app.state
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(_: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"Rate limit exceeded: {exc.detail}. "
                       "Lastenheft demo throttles per-IP to keep API costs predictable.",
        },
    )


_cors_origins = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(query.router)
app.include_router(session_router)
app.include_router(compliance.router)
