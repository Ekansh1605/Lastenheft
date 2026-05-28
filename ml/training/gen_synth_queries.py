"""
Synthetic query-passage pair generator for the BGE reranker fine-tune.

Pipeline:
    1. Pull all pages with substantive extracted_text from the corpus
       (skip pages with <200 chars — those are mostly cover pages / blank scans).
    2. Sample N pages, evenly across source brands.
    3. For each page, generate 3 questions via an LLM:
       - 1 short factual ("What is X?")
       - 1 multi-clause analytical ("Given Y, what is the X under Z?")
       - 1 in the opposite language from the source (DE-page -> EN question or vice-versa)
    4. Mine hard negatives via ColPali ANN (top-K closest pages excluding the positive).
    5. Emit a JSONL file: one record per training triple.

Output format (each line):
    {
        "query": "What is the operating voltage range of IndraDrive Cs?",
        "query_lang": "en",
        "positive_page_id": "uuid",
        "positive_filename": "bosch-rexroth-indradrive-cs-datasheet-en.pdf",
        "positive_page_number": 4,
        "negative_page_ids": ["uuid", "uuid", "uuid", "uuid", "uuid"],
        "source_lang": "en",
        "source_brand": "bosch-rexroth"
    }

Usage:
    ANTHROPIC_API_KEY=... uv run python -m ml.training.gen_synth_queries \
        --sample 250 --hard-negs 5 --out data/eval/synth_queries.jsonl

The fine-tuner reads this JSONL directly.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

# Ensure repo root is on path when invoked as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from ml.ingest.store import get_pool

log = logging.getLogger("synth-gen")
console = Console()

# ---------- LLM provider abstraction ----------

PROMPT_TEMPLATE = """You are generating training queries for an industrial-document retrieval system.

The document below is a page from a German industrial Mittelstand company (Siemens, Bosch, Festo, TRUMPF, KUKA, SICK, SEW, etc.) — a datasheet, manual, or technical brochure.

Generate exactly 3 questions a real engineer or technician would ask, that are ANSWERABLE ONLY from this page's content.

Rules:
1. Question 1: SHORT factual question (1 sentence, asks for a specific value / fact).
2. Question 2: ANALYTICAL question (1-2 sentences, requires combining multiple facts on the page).
3. Question 3: OPPOSITE LANGUAGE — if the page is in {source_lang}, write this question in {opposite_lang}. Should be a natural question a native speaker would ask.
4. Questions must be specific to THIS page. Avoid generic questions like "What is this product?" that could match many pages.
5. Use technical engineering vocabulary. The user is an engineer, not a layperson.
6. Output ONLY valid JSON. No prose, no markdown fences.

Output format:
{{"q1": "<short factual in {source_lang}>", "q2": "<analytical in {source_lang}>", "q3": "<question in {opposite_lang}>"}}

PAGE CONTENT (source language = {source_lang}):
---
{page_text}
---

JSON output:"""


def detect_lang(text: str, filename_hint: str | None = None) -> str:
    """Cheap heuristic: filename '-de' / '-en' hint, else simple word-bag."""
    if filename_hint:
        low = filename_hint.lower()
        if "-de." in low or "-de-" in low or "deutsch" in low or "manual_de" in low:
            return "de"
        if "-en." in low or "-en-" in low or "english" in low or "manual_en" in low:
            return "en"
    german_markers = {"der", "die", "das", "und", "mit", "für", "ist", "Sie", "ein", "eine", "von", "bei"}
    english_markers = {"the", "and", "with", "for", "is", "this", "you", "a", "an", "of", "to", "in"}
    words = {w.strip(".,;:()[]") for w in text.split()[:200]}
    de_score = len(words & german_markers)
    en_score = len(words & english_markers)
    return "de" if de_score > en_score else "en"


def call_anthropic(prompt: str, model: str = "claude-sonnet-4-6") -> str:
    import anthropic
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


def call_openai(prompt: str, model: str = "gpt-4o-mini") -> str:
    from openai import OpenAI
    client = OpenAI()
    resp = client.chat.completions.create(
        model=model,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content or ""


def llm_call(prompt: str, provider: str) -> str:
    if provider == "anthropic":
        return call_anthropic(prompt)
    if provider == "openai":
        return call_openai(prompt)
    raise ValueError(f"Unknown provider: {provider}")


def parse_response(text: str) -> dict[str, str] | None:
    """Extract the JSON object from the model's response. Lenient."""
    text = text.strip()
    # Strip markdown fences if the model added them
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(line for line in lines if not line.strip().startswith("```"))
    # Find first { ... } block
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not all(k in obj for k in ("q1", "q2", "q3")):
        return None
    return {k: str(v).strip() for k, v in obj.items() if isinstance(v, str | int | float)}


# ---------- DB access ----------

def fetch_candidate_pages(min_text_chars: int = 200) -> list[dict[str, Any]]:
    """Pull pages with substantive text + brand metadata."""
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                p.id::text          AS page_id,
                p.document_id::text AS document_id,
                p.page_number,
                p.extracted_text,
                d.filename,
                d.source            AS brand,
                d.language
            FROM pages p
            JOIN documents d ON d.id = p.document_id
            WHERE length(p.extracted_text) >= %s
            ORDER BY d.source, p.page_number
            """,
            (min_text_chars,),
        )
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def sample_evenly(pages: list[dict[str, Any]], n: int, key: str = "brand") -> list[dict[str, Any]]:
    """Stratified sample by brand so every brand contributes."""
    by_brand: dict[str, list] = defaultdict(list)
    for p in pages:
        by_brand[p.get(key) or "unknown"].append(p)
    per_brand = max(1, n // len(by_brand))
    picked: list[dict[str, Any]] = []
    for brand_pages in by_brand.values():
        random.shuffle(brand_pages)
        picked.extend(brand_pages[:per_brand])
    random.shuffle(picked)
    return picked[:n]


def mine_hard_negatives(page_id: str, k: int = 5) -> list[str]:
    """For a given positive page, find K closest OTHER pages by ColPali mean_vector distance."""
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            WITH q AS (SELECT mean_vector FROM page_embeddings WHERE page_id = %s)
            SELECT pe.page_id::text
            FROM page_embeddings pe, q
            WHERE pe.page_id <> %s
            ORDER BY pe.mean_vector <=> q.mean_vector
            LIMIT %s
            """,
            (page_id, page_id, k),
        )
        return [r[0] for r in cur.fetchall()]


# ---------- Main ----------

def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=250, help="Pages to sample")
    parser.add_argument("--hard-negs", type=int, default=5, help="Hard negatives per query")
    parser.add_argument("--out", type=Path, default=Path("data/eval/synth_queries.jsonl"))
    parser.add_argument("--provider", choices=["anthropic", "openai"], default=None,
                        help="LLM provider for query generation. Auto-detects from env if omitted.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    # Auto-pick provider based on which key is set
    provider = args.provider
    if provider is None:
        if os.getenv("ANTHROPIC_API_KEY"):
            provider = "anthropic"
        elif os.getenv("OPENAI_API_KEY"):
            provider = "openai"
        else:
            console.print("[red]No API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY.[/]")
            return 1
    console.print(f"[bold]Using provider:[/] {provider}")

    pages = fetch_candidate_pages()
    console.print(f"Loaded {len(pages)} candidate pages with text >= 200 chars")
    if not pages:
        console.print("[red]No pages available. Run bulk ingest first.[/]")
        return 1

    sampled = sample_evenly(pages, args.sample)
    console.print(f"Sampled {len(sampled)} pages stratified by brand")

    written = 0
    errors = 0
    started = time.time()
    with args.out.open("w", encoding="utf-8") as fp, Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Generating queries", total=len(sampled))
        for page in sampled:
            source_lang = page.get("language") or detect_lang(page["extracted_text"], page["filename"])
            opposite_lang = "en" if source_lang == "de" else "de"
            text_truncated = page["extracted_text"][:4000]  # cap context

            prompt = PROMPT_TEMPLATE.format(
                source_lang=source_lang,
                opposite_lang=opposite_lang,
                page_text=text_truncated,
            )

            try:
                raw = llm_call(prompt, provider)
                parsed = parse_response(raw)
            except Exception as e:  # noqa: BLE001
                log.warning("LLM call failed on page %s: %s", page["page_id"], e)
                errors += 1
                progress.advance(task)
                continue

            if not parsed:
                log.warning("Could not parse response for page %s: %s", page["page_id"], raw[:200])
                errors += 1
                progress.advance(task)
                continue

            try:
                negatives = mine_hard_negatives(page["page_id"], k=args.hard_negs)
            except Exception as e:  # noqa: BLE001
                log.warning("Hard-neg mining failed for page %s: %s", page["page_id"], e)
                negatives = []

            for qkey, query_lang in (("q1", source_lang), ("q2", source_lang), ("q3", opposite_lang)):
                query = parsed.get(qkey, "").strip()
                if not query or len(query) < 5:
                    continue
                record = {
                    "query": query,
                    "query_lang": query_lang,
                    "positive_page_id": page["page_id"],
                    "positive_filename": page["filename"],
                    "positive_page_number": page["page_number"],
                    "negative_page_ids": negatives,
                    "source_lang": source_lang,
                    "source_brand": page.get("brand"),
                }
                fp.write(json.dumps(record, ensure_ascii=False) + "\n")
                written += 1

            progress.advance(task)

    elapsed = time.time() - started
    console.print(f"\n[bold green]Wrote {written} queries[/] to {args.out} "
                  f"({errors} errors, {elapsed:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
