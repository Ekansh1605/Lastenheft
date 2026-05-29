"""
LLM router — picks local Qwen3 4B (sovereign default) or API LLM (escalation).

Every call returns the answer text PLUS metadata: provider, model, input/output
tokens, USD cost (0 for local), latency_ms. The audit log + Langfuse trace
record this per Article 13 of the EU AI Act (user must be informed which AI
generated the content).

API price estimates (May 2026, refresh periodically):
    Claude Sonnet 4.6  : $3.00 / 1M input,  $15.00 / 1M output
    GPT-4o            : $2.50 / 1M input,  $10.00 / 1M output
    Ollama (local)    : $0.00
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Literal

import httpx

# Qwen3 emits a chain-of-thought block even when asked to disable thinking.
# Sometimes wrapped in <think>...</think>, sometimes only the closing </think>
# is emitted with the opening implied. Strip both shapes.
_THINK_BLOCK_PAIRED = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)


def _strip_thinking(raw: str) -> str:
    """Pull the actual answer out from behind Qwen3's chain-of-thought."""
    # 1. Strip any complete <think>...</think> blocks
    cleaned = _THINK_BLOCK_PAIRED.sub("", raw).strip()
    # 2. If a stray </think> remains (open tag was implicit), take what's after the LAST one
    if "</think>" in cleaned.lower():
        cleaned = cleaned.rsplit("</think>", 1)[-1].strip()
        # Some models also have </Think> with capital T
        cleaned = re.split(r"</think>", cleaned, flags=re.IGNORECASE)[-1].strip()
    # 3. If the model wrapped output in stray <think> with no close, take what came before
    if "<think>" in cleaned.lower() and "</think>" not in cleaned.lower():
        cleaned = re.split(r"<think>", cleaned, flags=re.IGNORECASE, maxsplit=1)[0].strip()
    return cleaned or raw  # fallback: never return empty if model produced anything

log = logging.getLogger("lastenheft.llm")

Provider = Literal["anthropic", "openai", "ollama-local"]


@dataclass(slots=True)
class LLMResponse:
    text: str
    provider: Provider
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int


# Per-1M-token prices (USD). Update as providers change pricing.
_PRICES = {
    "anthropic": {
        "claude-sonnet-4-6": (3.00, 15.00),
        "claude-opus-4-7":   (15.00, 75.00),
        "claude-haiku-4-5":  (0.80, 4.00),
    },
    "openai": {
        "gpt-4o":      (2.50, 10.00),
        "gpt-4o-mini": (0.15, 0.60),
    },
    "ollama-local": {},
}


def _cost(provider: Provider, model: str, input_tokens: int, output_tokens: int) -> float:
    table = _PRICES.get(provider, {})
    if model not in table:
        return 0.0
    in_price, out_price = table[model]
    return (input_tokens / 1_000_000) * in_price + (output_tokens / 1_000_000) * out_price


# ---------------- providers ----------------

def _call_anthropic(prompt: str, model: str, system: str | None,
                    max_tokens: int) -> LLMResponse:
    import anthropic
    client = anthropic.Anthropic()
    t0 = time.perf_counter()
    kwargs = {"model": model, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": prompt}]}
    if system:
        kwargs["system"] = system
    resp = client.messages.create(**kwargs)
    latency = int((time.perf_counter() - t0) * 1000)
    text = resp.content[0].text if resp.content else ""
    in_tok = resp.usage.input_tokens
    out_tok = resp.usage.output_tokens
    return LLMResponse(
        text=text, provider="anthropic", model=model,
        input_tokens=in_tok, output_tokens=out_tok,
        cost_usd=_cost("anthropic", model, in_tok, out_tok),
        latency_ms=latency,
    )


def _call_openai(prompt: str, model: str, system: str | None,
                 max_tokens: int) -> LLMResponse:
    from openai import OpenAI
    client = OpenAI()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    t0 = time.perf_counter()
    resp = client.chat.completions.create(
        model=model, max_tokens=max_tokens, messages=messages,
    )
    latency = int((time.perf_counter() - t0) * 1000)
    text = resp.choices[0].message.content or ""
    in_tok = resp.usage.prompt_tokens
    out_tok = resp.usage.completion_tokens
    return LLMResponse(
        text=text, provider="openai", model=model,
        input_tokens=in_tok, output_tokens=out_tok,
        cost_usd=_cost("openai", model, in_tok, out_tok),
        latency_ms=latency,
    )


def _call_ollama(prompt: str, model: str, system: str | None,
                 max_tokens: int) -> LLMResponse:
    """Local sovereign default. Disables Qwen3's 'thinking' mode for short answers."""
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    # Qwen3 still leaks chain-of-thought under Ollama's `think: false`. Prepending
    # `/no_think` in the prompt is the documented hard-disable for the family.
    if "qwen3" in model.lower() and not prompt.lstrip().startswith("/no_think"):
        prompt = "/no_think\n" + prompt
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {"num_predict": max_tokens, "temperature": 0.2},
    }
    if system:
        body["system"] = system

    t0 = time.perf_counter()
    with httpx.Client(timeout=180.0) as client:
        r = client.post(f"{host}/api/generate", json=body)
        r.raise_for_status()
        data = r.json()
    latency = int((time.perf_counter() - t0) * 1000)
    raw = (data.get("response") or "").strip()
    text = _strip_thinking(raw)
    in_tok = int(data.get("prompt_eval_count") or 0)
    out_tok = int(data.get("eval_count") or 0)
    return LLMResponse(
        text=text, provider="ollama-local", model=model,
        input_tokens=in_tok, output_tokens=out_tok,
        cost_usd=0.0, latency_ms=latency,
    )


# ---------------- router ----------------

def _api_llm_allowed() -> bool:
    """Hard kill-switch. When false, ALL sovereignty modes downgrade to local.
    Set ALLOW_API_LLM=false in public deploys to prevent API cost drain."""
    return os.getenv("ALLOW_API_LLM", "true").lower() not in ("false", "0", "no")


def pick_provider(sovereignty_mode: str, needs_escalation: bool) -> tuple[Provider, str]:
    """Decide which provider + model to use. Logged for AI Act Art. 13 transparency."""
    if not _api_llm_allowed():
        if sovereignty_mode != "local-only":
            log.info("ALLOW_API_LLM=false; forcing local-only despite mode=%s", sovereignty_mode)
        return "ollama-local", os.getenv("OLLAMA_MODEL", "qwen3:4b")
    if sovereignty_mode == "local-only":
        return "ollama-local", os.getenv("OLLAMA_MODEL", "qwen3:4b")
    if sovereignty_mode == "api-only":
        # Prefer Anthropic if key present, else OpenAI
        if os.getenv("ANTHROPIC_API_KEY"):
            return "anthropic", os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        return "openai", os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    # hybrid (default)
    if needs_escalation:
        if os.getenv("ANTHROPIC_API_KEY"):
            return "anthropic", os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        if os.getenv("OPENAI_API_KEY"):
            return "openai", os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        # Fallback to local even if escalation requested but no API keys available
        log.warning("Escalation requested but no API keys configured; staying local")
    return "ollama-local", os.getenv("OLLAMA_MODEL", "qwen3:4b")


def generate(prompt: str, sovereignty_mode: str, needs_escalation: bool = False,
             system: str | None = None, max_tokens: int = 800) -> LLMResponse:
    """Route to the chosen provider and run a single generation.

    If an API provider fails (invalid key, rate limit, network), fall back to
    Ollama-local so the user gets *some* answer rather than a stack trace.
    Every fallback is logged so the audit trail still tells the truth.
    """
    provider, model = pick_provider(sovereignty_mode, needs_escalation)
    log.info("routing -> provider=%s model=%s escalation=%s mode=%s",
             provider, model, needs_escalation, sovereignty_mode)
    try:
        if provider == "anthropic":
            return _call_anthropic(prompt, model, system, max_tokens)
        if provider == "openai":
            return _call_openai(prompt, model, system, max_tokens)
        return _call_ollama(prompt, model, system, max_tokens)
    except Exception as e:  # noqa: BLE001 — fallback is the point
        if provider == "ollama-local":
            raise  # local already failed; nothing better to try
        log.warning("LLM provider %s failed (%s) — falling back to ollama-local",
                    provider, type(e).__name__)
        fallback_model = os.getenv("OLLAMA_MODEL", "qwen3:4b")
        resp = _call_ollama(prompt, fallback_model, system, max_tokens)
        # Tag the response so the audit log reflects that this was a fallback
        return LLMResponse(
            text=resp.text,
            provider="ollama-local",
            model=f"{fallback_model} (fallback from {provider})",
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            cost_usd=resp.cost_usd,
            latency_ms=resp.latency_ms,
        )
