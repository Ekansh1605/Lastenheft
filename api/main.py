"""FastAPI entrypoint for the WerkDocs ML orchestration layer."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import compliance, health, ingest, query

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
)
log = logging.getLogger("werkdocs.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("WerkDocs API starting (env=%s)", os.getenv("APP_ENV", "development"))
    yield
    log.info("WerkDocs API shutting down")


app = FastAPI(
    title="WerkDocs API",
    version="0.1.0",
    description="Sovereign multimodal document intelligence for industrial manufacturing.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(query.router)
app.include_router(compliance.router)
