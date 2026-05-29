"""
Retrieval eval harness.

For each held-out synthetic query, compare three retrieval strategies:

    1. BASELINE     : ColPali ANN over full corpus -> mean-vector cosine top-K
    2. BASE-RERANK  : ColPali top-50 -> BGE-reranker-v2-m3 OFF-THE-SHELF rerank -> top-K
    3. LORA-RERANK  : ColPali top-50 -> BGE-reranker-v2-m3 + LoRA fine-tune -> top-K

Metrics (over the held-out queries):
    - MRR              : Mean Reciprocal Rank of the positive page
    - Hit@1, Hit@5     : fraction of queries where the positive is at rank <= K
    - nDCG@10          : normalized discounted cumulative gain at 10

This is the script that produces the table you'll cite in the README and in
interviews. Numbers should beat baseline meaningfully — that's the proof
that the fine-tune actually moved the needle.

Usage:
    uv run python -m ml.training.eval_retrieval \
        --synth data/eval/synth_queries.jsonl \
        --eval-split 0.1 \
        --base BAAI/bge-reranker-v2-m3 \
        --lora models/reranker-lora \
        --out  data/eval/retrieval_results.json
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import random
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

import torch
from peft import PeftModel
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from ml.ingest.embedder import embed_query
from ml.ingest.store import ann_search_pages, get_pool

log = logging.getLogger("eval-retrieval")
console = Console()


# ---------- metrics ----------

def mrr(ranks: list[int]) -> float:
    if not ranks:
        return 0.0
    return sum(1.0 / r for r in ranks if r > 0) / len(ranks)


def hit_at_k(ranks: list[int], k: int) -> float:
    if not ranks:
        return 0.0
    return sum(1 for r in ranks if 0 < r <= k) / len(ranks)


def ndcg_at_10(ranks: list[int]) -> float:
    """For binary relevance with a single positive, nDCG@10 = 1/log2(rank+1) if rank<=10 else 0."""
    if not ranks:
        return 0.0
    return sum(1.0 / math.log2(r + 1) for r in ranks if 0 < r <= 10) / len(ranks)


# ---------- data helpers ----------

def load_held_out(synth_path: Path, split: float, seed: int = 42) -> list[dict]:
    records = [json.loads(line) for line in synth_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    random.Random(seed).shuffle(records)
    split_idx = int(len(records) * (1 - split))
    return records[split_idx:]


def fetch_page_texts(page_ids: Iterable[str]) -> dict[str, str]:
    ids = list(page_ids)
    if not ids:
        return {}
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id::text, extracted_text FROM pages WHERE id::text = ANY(%s)", (ids,))
        return {row[0]: row[1] or "" for row in cur.fetchall()}


# ---------- rerankers ----------

class Reranker:
    def __init__(self, base: str, lora_path: Path | None = None, device: str = "cuda"):
        dtype = torch.bfloat16 if device == "cuda" else torch.float32
        self.tok = AutoTokenizer.from_pretrained(base)
        model = AutoModelForSequenceClassification.from_pretrained(base, num_labels=1, torch_dtype=dtype)
        if lora_path is not None:
            model = PeftModel.from_pretrained(model, str(lora_path))
        self.model = model.to(device).eval()
        self.device = device

    @torch.inference_mode()
    def score(self, query: str, passages: list[str], batch_size: int = 16) -> list[float]:
        scores: list[float] = []
        for i in range(0, len(passages), batch_size):
            chunk = passages[i : i + batch_size]
            enc = self.tok([query] * len(chunk), chunk, padding=True, truncation=True,
                           max_length=512, return_tensors="pt").to(self.device)
            out = self.model(**enc)
            logit = out.logits.squeeze(-1) if out.logits.dim() == 2 else out.logits
            scores.extend(logit.float().cpu().tolist())
        return scores


# ---------- evaluation runners ----------

def rank_of_positive(ranked_ids: list[str], positive_id: str) -> int:
    """1-indexed rank; 0 if not in the list (i.e. miss)."""
    try:
        return ranked_ids.index(positive_id) + 1
    except ValueError:
        return 0


def evaluate(synth_path: Path, eval_split: float, base_model: str,
             lora_path: Path | None, candidate_k: int = 50) -> dict[str, Any]:
    queries = load_held_out(synth_path, eval_split)
    console.print(f"[bold]Held-out queries:[/] {len(queries)}")

    device = "cuda" if torch.cuda.is_available() else "cpu"

    console.print("Loading BASE reranker (off-the-shelf BGE)...")
    base_reranker = Reranker(base_model, lora_path=None, device=device)

    lora_reranker: Reranker | None = None
    if lora_path and lora_path.exists():
        console.print(f"Loading LORA reranker from {lora_path}...")
        lora_reranker = Reranker(base_model, lora_path=lora_path, device=device)
    else:
        console.print("[yellow]No LoRA checkpoint found - LORA-RERANK row will be skipped[/]")

    results = {"baseline": [], "base_rerank": [], "lora_rerank": []}

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  TimeElapsedColumn(), console=console) as progress:
        task = progress.add_task("Evaluating", total=len(queries))
        for q in queries:
            query = q["query"]
            positive_id = q["positive_page_id"]

            # 1. ColPali ANN over corpus
            q_vec = embed_query(query)
            ann_hits = ann_search_pages(q_vec, top_k=candidate_k)
            ann_ids = [h["page_id"] for h in ann_hits]
            results["baseline"].append(rank_of_positive(ann_ids, positive_id))

            # Pull text for the top-K so we can rerank
            page_texts = fetch_page_texts(ann_ids)
            passages = [page_texts.get(pid, "") for pid in ann_ids]

            # 2. base BGE rerank
            scores = base_reranker.score(query, passages)
            ranked_ids_base = [pid for _, pid in sorted(zip(scores, ann_ids, strict=True), reverse=True)]
            results["base_rerank"].append(rank_of_positive(ranked_ids_base, positive_id))

            # 3. LoRA rerank
            if lora_reranker:
                scores = lora_reranker.score(query, passages)
                ranked_ids_lora = [pid for _, pid in sorted(zip(scores, ann_ids, strict=True), reverse=True)]
                results["lora_rerank"].append(rank_of_positive(ranked_ids_lora, positive_id))

            progress.advance(task)

    summary = {}
    for name, ranks in results.items():
        if not ranks:
            continue
        summary[name] = {
            "n_queries": len(ranks),
            "mrr": round(mrr(ranks), 4),
            "hit@1": round(hit_at_k(ranks, 1), 4),
            "hit@5": round(hit_at_k(ranks, 5), 4),
            "hit@10": round(hit_at_k(ranks, 10), 4),
            "ndcg@10": round(ndcg_at_10(ranks), 4),
            "median_rank": int(sorted(ranks)[len(ranks) // 2]) if ranks else 0,
            "misses": sum(1 for r in ranks if r == 0),
        }
    return summary


def render_table(summary: dict[str, Any]) -> None:
    t = Table(title="Retrieval evaluation results")
    t.add_column("strategy", style="cyan")
    for col in ["n", "MRR", "Hit@1", "Hit@5", "Hit@10", "nDCG@10", "median rank", "misses"]:
        t.add_column(col, justify="right")
    for name in ("baseline", "base_rerank", "lora_rerank"):
        if name not in summary:
            continue
        s = summary[name]
        t.add_row(name,
                  str(s["n_queries"]), f"{s['mrr']:.3f}", f"{s['hit@1']:.3f}",
                  f"{s['hit@5']:.3f}", f"{s['hit@10']:.3f}", f"{s['ndcg@10']:.3f}",
                  str(s["median_rank"]), str(s["misses"]))
    console.print(t)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--synth", type=Path, default=Path("data/eval/synth_queries.jsonl"))
    parser.add_argument("--eval-split", type=float, default=0.1)
    parser.add_argument("--base", default="BAAI/bge-reranker-v2-m3")
    parser.add_argument("--lora", type=Path, default=Path("models/reranker-lora"))
    parser.add_argument("--candidate-k", type=int, default=50)
    parser.add_argument("--out", type=Path, default=Path("data/eval/retrieval_results.json"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    summary = evaluate(args.synth, args.eval_split, args.base,
                       args.lora if args.lora.exists() else None, args.candidate_k)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2))
    render_table(summary)
    console.print(f"\nSaved -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
