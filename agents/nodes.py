"""
LangGraph nodes for the Lastenheft retrieval-augmented Q&A flow.

    user query
        |
        v
    planner    (decompose if complex, score complexity)
        |
        v
    retriever  (ColPali ANN -> BGE LoRA rerank, per sub-query)
        |
        v
    validator  (does retrieved evidence cover the query? escalate?)
        |
        v
    synthesizer (cite-everything answer via local Qwen3 or escalation LLM)

Every node returns a partial AgentState update and appends a TraceEvent.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from agents.llm_router import generate
from agents.state import AgentState, Citation, TraceEvent
from ml.ingest.embedder import embed_query
from ml.ingest.store import ann_search_pages, get_pool
from ml.retrieval.reranker import rerank, model_label

log = logging.getLogger("lastenheft.agents")

ANN_K = 50
RERANK_K = 5


# ---------- helpers ----------

def _trace(state: AgentState, step: str, detail: str, t0: float,
           payload: dict[str, Any] | None = None) -> TraceEvent:
    return TraceEvent(
        step=step, detail=detail, payload=payload or {},
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )


def _extract_json(text: str) -> dict | None:
    """Pull the first {...} JSON object out of LLM output. Lenient to fences/prose."""
    text = text.strip()
    if text.startswith("```"):
        text = "\n".join(line for line in text.splitlines() if not line.strip().startswith("```"))
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _fetch_page_meta(page_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Look up filename, page_number, extracted_text by page_id."""
    if not page_ids:
        return {}
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.id::text, p.document_id::text, p.page_number, p.extracted_text,
                   d.filename
            FROM pages p
            JOIN documents d ON d.id = p.document_id
            WHERE p.id::text = ANY(%s)
            """,
            (page_ids,),
        )
        return {row[0]: {
            "document_id": row[1], "page_number": row[2],
            "extracted_text": row[3] or "", "filename": row[4],
        } for row in cur.fetchall()}


# ---------- planner ----------

PLANNER_SYSTEM = (
    "You decompose user queries about technical industrial documentation. "
    "Output strict JSON only — no markdown, no prose."
)

PLANNER_TEMPLATE = """Decide if this query can be answered with a single document lookup or
needs to be decomposed into multiple sub-questions.

Examples:
- "What is the operating voltage of the SIMATIC S7-1200?" -> simple, 1 sub-query, complexity 0.1
- "Compare the maximum sheet thickness across Trumpf TruLaser 1030 and 2030 for stainless steel" -> complex, 2 sub-queries, complexity 0.7
- "Which Festo cylinders are ISO 15552 compliant AND have stroke length > 1000 mm?" -> complex, 2 sub-queries (compliance + stroke), complexity 0.6

USER QUERY:
{query}

Return JSON in exactly this shape:
{{"sub_queries": ["...", "..."], "complexity": 0.0, "rationale": "one sentence"}}

JSON:"""


def planner(state: AgentState) -> AgentState:
    t0 = time.perf_counter()
    query = state["query"]
    prompt = PLANNER_TEMPLATE.format(query=query)
    resp = generate(prompt, state.get("sovereignty_mode", "hybrid"),
                    needs_escalation=False,
                    system=PLANNER_SYSTEM, max_tokens=300)
    parsed = _extract_json(resp.text) or {}
    sub_queries = parsed.get("sub_queries") or [query]
    if not isinstance(sub_queries, list) or not sub_queries:
        sub_queries = [query]
    complexity = float(parsed.get("complexity", 0.3) or 0.3)
    rationale = str(parsed.get("rationale", ""))[:300]

    update: AgentState = {
        "sub_queries": [str(q)[:300] for q in sub_queries[:5]],
        "complexity_score": min(max(complexity, 0.0), 1.0),
        "plan_rationale": rationale,
    }
    update["trace"] = [_trace(state, "planner",
                              f"decomposed into {len(sub_queries)} sub-queries (complexity={complexity:.2f})",
                              t0, {"provider": resp.provider, "model": resp.model,
                                   "tokens_in": resp.input_tokens, "tokens_out": resp.output_tokens,
                                   "cost_usd": resp.cost_usd})]
    return update


# ---------- retriever ----------

def retriever(state: AgentState) -> AgentState:
    t0 = time.perf_counter()
    sub_queries = state.get("sub_queries") or [state["query"]]

    # ANN over all sub-queries, then merge candidates
    candidates: dict[str, dict[str, Any]] = {}
    for q in sub_queries:
        q_vec = embed_query(q)
        hits = ann_search_pages(q_vec, top_k=ANN_K)
        for h in hits:
            pid = h["page_id"]
            # Keep the highest ANN score across sub-queries
            if pid not in candidates or h["score"] > candidates[pid]["ann_score"]:
                candidates[pid] = {**h, "ann_score": h["score"]}

    if not candidates:
        return {
            "retrieved": [],
            "trace": [_trace(state, "retriever", "no candidates from ANN", t0)],
        }

    # Hydrate text for reranker input
    cand_ids = list(candidates.keys())
    metas = _fetch_page_meta(cand_ids)

    # Use the primary query for rerank — sub-queries already biased the candidate set
    passages = [metas.get(pid, {}).get("extracted_text", "") for pid in cand_ids]
    ranked = rerank(state["query"], passages, top_k=RERANK_K)

    citations: list[Citation] = []
    for idx, score in ranked:
        pid = cand_ids[idx]
        meta = metas.get(pid, {})
        text = (meta.get("extracted_text") or "")[:800]
        citations.append(Citation(
            page_id=pid,
            document_id=meta.get("document_id", ""),
            filename=meta.get("filename", ""),
            page_number=int(meta.get("page_number", 0)),
            score=float(score),
            snippet=text,
        ))

    update: AgentState = {
        "candidate_page_ids": cand_ids,
        "retrieved": citations,
        "trace": [_trace(state, "retriever",
                         f"ANN={len(cand_ids)} candidates, reranked to top-{len(citations)}",
                         t0, {"reranker": model_label(), "ann_k": ANN_K, "rerank_k": RERANK_K})],
    }
    return update


# ---------- validator ----------

VALIDATOR_SYSTEM = (
    "You assess whether retrieved document snippets contain enough evidence to answer a query. "
    "Output strict JSON only."
)

VALIDATOR_TEMPLATE = """Query: {query}

Retrieved page snippets:
{snippets}

Rate from 0.0 (no evidence) to 1.0 (clearly contains the answer) how confidently the answer
is supported by these snippets. Also decide if generating a good answer requires complex
multi-step reasoning beyond simple lookup (e.g. cross-page comparison, numeric calculation).

Return JSON:
{{"coverage": 0.0, "needs_reasoning": false, "notes": "one sentence"}}

JSON:"""


def validator(state: AgentState) -> AgentState:
    t0 = time.perf_counter()
    citations = state.get("retrieved") or []
    if not citations:
        return {
            "coverage_confidence": 0.0,
            "needs_escalation": False,
            "validation_notes": "no candidates retrieved",
            "trace": [_trace(state, "validator", "no candidates to validate", t0)],
        }

    snippets = "\n\n".join(
        f"[{i+1}] ({c['filename']} p.{c['page_number']}) {c['snippet']}"
        for i, c in enumerate(citations[:RERANK_K])
    )
    prompt = VALIDATOR_TEMPLATE.format(query=state["query"], snippets=snippets)
    resp = generate(prompt, state.get("sovereignty_mode", "hybrid"),
                    needs_escalation=False,
                    system=VALIDATOR_SYSTEM, max_tokens=200)
    parsed = _extract_json(resp.text) or {}
    coverage = float(parsed.get("coverage", 0.5) or 0.5)
    needs_reasoning = bool(parsed.get("needs_reasoning", False))
    notes = str(parsed.get("notes", ""))[:300]

    sovereignty = state.get("sovereignty_mode", "hybrid")
    escalate = needs_reasoning and sovereignty == "hybrid"

    update: AgentState = {
        "coverage_confidence": min(max(coverage, 0.0), 1.0),
        "needs_escalation": escalate,
        "validation_notes": notes,
        "trace": [_trace(state, "validator",
                         f"coverage={coverage:.2f} escalate={escalate}",
                         t0, {"provider": resp.provider, "model": resp.model,
                              "needs_reasoning": needs_reasoning,
                              "tokens_in": resp.input_tokens, "tokens_out": resp.output_tokens})],
    }
    return update


# ---------- synthesizer ----------

SYNTH_SYSTEM = (
    "You answer questions about industrial technical documentation using ONLY the provided "
    "page snippets. Cite every fact with the bracketed source like [1] or [2]. If the "
    "snippets do not contain the answer, say so explicitly — do NOT make up information."
)

SYNTH_TEMPLATE = """Question: {query}

Source pages:
{snippets}

Answer the question, citing the source numbers in [brackets] for each fact.
If the sources don't contain the answer, say "The provided sources do not contain this information."

Answer:"""


def synthesizer(state: AgentState) -> AgentState:
    t0 = time.perf_counter()
    citations = state.get("retrieved") or []
    if not citations:
        return {
            "answer": "The provided sources do not contain this information.",
            "llm_provider": "ollama-local",
            "llm_model": "n/a",
            "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
            "trace": [_trace(state, "synthesizer", "no citations -> empty answer", t0)],
        }

    snippets = "\n\n".join(
        f"[{i+1}] ({c['filename']} p.{c['page_number']}) {c['snippet']}"
        for i, c in enumerate(citations[:RERANK_K])
    )
    prompt = SYNTH_TEMPLATE.format(query=state["query"], snippets=snippets)
    # Bigger token budget for local Qwen3 because the model spends most tokens
    # on its <think> block before producing the actual answer.
    resp = generate(prompt, state.get("sovereignty_mode", "hybrid"),
                    needs_escalation=bool(state.get("needs_escalation")),
                    system=SYNTH_SYSTEM, max_tokens=1500)
    update: AgentState = {
        "answer": resp.text.strip(),
        "llm_provider": resp.provider,
        "llm_model": resp.model,
        "input_tokens": resp.input_tokens,
        "output_tokens": resp.output_tokens,
        "cost_usd": resp.cost_usd,
        "trace": [_trace(state, "synthesizer",
                         f"answer via {resp.provider}/{resp.model} ({resp.output_tokens} tokens, ${resp.cost_usd:.4f})",
                         t0, {"provider": resp.provider, "model": resp.model,
                              "tokens_in": resp.input_tokens, "tokens_out": resp.output_tokens,
                              "cost_usd": resp.cost_usd, "latency_ms": resp.latency_ms,
                              "escalated": bool(state.get("needs_escalation"))})],
    }
    return update
