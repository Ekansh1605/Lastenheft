"""
Lazy Langfuse client for the Lastenheft agent.

When `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` are set, we initialise a
real client and the helpers below emit traces / generations / spans to it.
When they're not, every call is a silent no-op so dev / demo runs don't
require Langfuse to be configured.

Why a thin custom wrapper rather than @observe:
    * LangGraph wraps each node in its own runnable, which breaks the
      decorator's call-stack assumption.
    * We already collect provider/model/tokens/cost/latency for the audit log.
      The helpers below just forward that same data into Langfuse spans so
      one source of truth feeds both the in-DB audit trail and the Langfuse UI.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

log = logging.getLogger("lastenheft.langfuse")


@lru_cache(maxsize=1)
def _client():
    public = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    secret = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    host = os.getenv("LANGFUSE_HOST", "http://localhost:3001").strip()
    if not public or not secret or public.startswith(("pk-lf-...", "REPLACE")):
        log.info("Langfuse not configured (LANGFUSE_PUBLIC_KEY / SECRET_KEY missing). Tracing disabled.")
        return None
    try:
        from langfuse import Langfuse
        client = Langfuse(public_key=public, secret_key=secret, host=host)
        log.info("Langfuse client initialised: %s", host)
        return client
    except Exception as e:  # noqa: BLE001 — Langfuse is best-effort
        log.warning("Langfuse init failed (%s) — continuing without tracing", e)
        return None


@contextmanager
def trace(name: str, session_id: str | None = None, user_id: str | None = None,
          metadata: dict[str, Any] | None = None):
    """Yield a Langfuse trace handle or None. Always safe to call."""
    client = _client()
    if client is None:
        yield None
        return
    try:
        t = client.trace(name=name, session_id=session_id, user_id=user_id,
                         metadata=metadata or {})
    except Exception as e:  # noqa: BLE001
        log.debug("langfuse.trace() failed: %s", e)
        yield None
        return
    try:
        yield t
    finally:
        try:
            client.flush()
        except Exception:  # noqa: BLE001
            pass


def log_generation(parent, *, name: str, model: str, input_text: str,
                   output_text: str, input_tokens: int = 0,
                   output_tokens: int = 0, latency_ms: int = 0,
                   metadata: dict[str, Any] | None = None) -> None:
    """Record one LLM call against the active trace. No-op if Langfuse disabled."""
    if parent is None:
        return
    try:
        parent.generation(
            name=name, model=model,
            input=input_text[:4000],
            output=output_text[:4000],
            usage_details={
                "input": int(input_tokens or 0),
                "output": int(output_tokens or 0),
            },
            metadata={"latency_ms": int(latency_ms or 0), **(metadata or {})},
        )
    except Exception as e:  # noqa: BLE001
        log.debug("langfuse.generation() failed: %s", e)


def log_span(parent, *, name: str, latency_ms: int,
             input_data: Any = None, output_data: Any = None,
             metadata: dict[str, Any] | None = None) -> None:
    """Record one non-LLM agent step (planner / retriever / validator) as a span."""
    if parent is None:
        return
    try:
        parent.span(
            name=name,
            input=input_data, output=output_data,
            metadata={"latency_ms": int(latency_ms or 0), **(metadata or {})},
        )
    except Exception as e:  # noqa: BLE001
        log.debug("langfuse.span() failed: %s", e)
