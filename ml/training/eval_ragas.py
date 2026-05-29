"""
RAGAS end-to-end evaluation: faithfulness + answer relevancy + context precision.

Where retrieval eval (eval_retrieval.py) measures whether the right page made
it to the top of the candidate list, RAGAS measures whether the GENERATED
ANSWER is grounded in the cited context and actually addresses the query.

Pipeline per held-out query:
    1. Run the full agent (graph.invoke) to get answer + citations
    2. Score the answer with RAGAS metrics against
       (query, generated_answer, retrieved_contexts, ground_truth_context)
    3. Aggregate.

NOTE on cost: each query runs the agent (which calls Qwen3 or API LLM) AND
the RAGAS metrics make LLM calls too. Default config uses Anthropic for both,
so a 50-query sample is roughly $1-2.

Usage:
    uv run python -m ml.training.eval_ragas \
        --synth data/eval/synth_queries.remapped.jsonl \
        --sample 50 \
        --mode hybrid \
        --out data/eval/ragas_results.json
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

# Ensure compat shim is applied before any ragas/langchain import
import ml.compat  # noqa: F401

from datasets import Dataset
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.metrics import answer_relevancy, context_precision, faithfulness
from rich.console import Console
from rich.table import Table

from agents.graph import get_graph
from ml.ingest.store import get_pool

log = logging.getLogger("eval-ragas")
console = Console()


def fetch_page_text(page_id: str) -> str:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT extracted_text FROM pages WHERE id::text = %s", (page_id,))
        row = cur.fetchone()
        return (row[0] or "") if row else ""


def load_eval_set(synth_path: Path, sample: int, seed: int = 42) -> list[dict]:
    records = [json.loads(line) for line in synth_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    random.Random(seed).shuffle(records)
    return records[:sample]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--synth", type=Path, default=Path("data/eval/synth_queries.remapped.jsonl"))
    parser.add_argument("--sample", type=int, default=50)
    parser.add_argument("--mode", choices=["local-only", "hybrid", "api-only"], default="hybrid")
    parser.add_argument("--out", type=Path, default=Path("data/eval/ragas_results.json"))
    args = parser.parse_args()

    queries = load_eval_set(args.synth, args.sample)
    console.print(f"[bold]Eval queries:[/] {len(queries)} (mode={args.mode})")

    graph = get_graph()

    rows = []
    t_start = time.time()
    for i, q in enumerate(queries, 1):
        console.print(f"[dim]({i}/{len(queries)})[/] {q['query'][:90]}")
        try:
            state = graph.invoke({
                "query": q["query"],
                "sovereignty_mode": args.mode,
                "trace": [],
            })
            answer = state.get("answer", "")
            citations = state.get("retrieved", [])
            contexts = [c.get("snippet", "") for c in citations] or [""]
            ground_truth = fetch_page_text(q["positive_page_id"])[:1500]
            rows.append({
                "user_input": q["query"],
                "response": answer,
                "retrieved_contexts": contexts,
                "reference": ground_truth,
                "_positive_filename": q["positive_filename"],
                "_positive_page": q["positive_page_number"],
            })
        except Exception as e:  # noqa: BLE001
            log.warning("agent failed on query %d: %s", i, e)
    elapsed = time.time() - t_start
    console.print(f"[bold]Agent runs done in {elapsed:.1f}s, scoring with RAGAS...[/]")

    if not rows:
        console.print("[red]No successful agent runs to score.[/]")
        return 1

    # Build the dataset RAGAS expects
    ds = Dataset.from_list([{
        "user_input": r["user_input"],
        "response": r["response"],
        "retrieved_contexts": r["retrieved_contexts"],
        "reference": r["reference"],
    } for r in rows])

    # RAGAS judge LLM + embeddings. Use Claude Sonnet (we already have key).
    import os
    if os.getenv("ANTHROPIC_API_KEY"):
        judge_llm = LangchainLLMWrapper(ChatAnthropic(model="claude-sonnet-4-6", temperature=0.0))
    else:
        judge_llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini", temperature=0.0))
    judge_embed = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model="text-embedding-3-small")) \
        if os.getenv("OPENAI_API_KEY") else None

    metrics = [faithfulness, answer_relevancy]
    if judge_embed:
        metrics.append(context_precision)

    result = evaluate(ds, metrics=metrics, llm=judge_llm, embeddings=judge_embed,
                      raise_exceptions=False)
    scores = {k: float(v) for k, v in result.to_pandas().mean(numeric_only=True).items()}

    summary = {
        "n": len(rows),
        "mode": args.mode,
        "metrics": scores,
        "agent_run_seconds": round(elapsed, 1),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2))

    t = Table(title=f"RAGAS scores (n={len(rows)}, mode={args.mode})")
    t.add_column("metric", style="cyan")
    t.add_column("score", justify="right")
    for k, v in scores.items():
        t.add_row(k, f"{v:.3f}")
    console.print(t)
    console.print(f"Saved -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
