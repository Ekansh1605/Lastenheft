"""
LoRA fine-tune of BAAI/bge-reranker-v2-m3 on the synthetic
query/positive/hard-negative triples produced by gen_synth_queries.py.

Why this matters for the project:
    - ColPali handles visual retrieval (top-K candidates).
    - A cross-encoder reranker then re-scores those candidates against the
      QUERY TEXT, which is much more sensitive to wording than vector ANN.
    - Fine-tuning the reranker on domain-specific (industrial DE+EN technical)
      queries is where the real "trained ML on your data" story lives —
      this is the DS-Engineer signal in the README.

Training objective:
    Listwise InfoNCE — for each query, score (query, positive_passage) plus
    N (query, hard_negative_passage) pairs, then cross-entropy where the
    positive must outscore all negatives.

VRAM budget on RTX 3060 6GB:
    BGE-reranker-v2-m3 = 568M params (XLM-RoBERTa-large base)
    bf16 inference + LoRA training fits in ~3-4GB.

Usage:
    uv run python -m ml.training.train_reranker \
        --synth data/eval/synth_queries.jsonl \
        --out  models/reranker-lora \
        --epochs 3 --batch 8 --lr 2e-4 --eval-split 0.1
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

import numpy as np
import torch
import torch.nn.functional as F
from peft import LoraConfig, TaskType, get_peft_model
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from ml.ingest.store import get_pool

log = logging.getLogger("train-reranker")
console = Console()

DEFAULT_BASE = "BAAI/bge-reranker-v2-m3"
MAX_LEN = int(os.getenv("RERANKER_MAX_LEN", "512"))


# ---------- data loading ----------

@dataclass
class Example:
    query: str
    positive_text: str
    negative_texts: list[str]


def fetch_page_texts(page_ids: list[str]) -> dict[str, str]:
    """Bulk-fetch extracted_text for a set of page UUIDs."""
    if not page_ids:
        return {}
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id::text, extracted_text FROM pages WHERE id::text = ANY(%s)",
            (page_ids,),
        )
        return {row[0]: row[1] or "" for row in cur.fetchall()}


def load_synth_dataset(path: Path, max_negs: int = 4) -> list[Example]:
    """Hydrate JSONL records with actual page text from DB."""
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    all_page_ids: set[str] = set()
    for r in records:
        all_page_ids.add(r["positive_page_id"])
        all_page_ids.update(r.get("negative_page_ids", []))
    texts = fetch_page_texts(list(all_page_ids))

    examples: list[Example] = []
    skipped_pos = skipped_neg = 0
    for r in records:
        pos = texts.get(r["positive_page_id"], "").strip()
        if not pos:
            skipped_pos += 1
            continue
        # Only keep negatives with substantive text. Pull more than needed so we can
        # backfill if some are empty, then require exactly max_negs after filtering.
        all_neg_ids = r.get("negative_page_ids", [])
        negs = [t.strip() for t in (texts.get(nid, "") for nid in all_neg_ids) if t.strip()]
        if len(negs) < max_negs:
            skipped_neg += 1
            continue
        examples.append(Example(query=r["query"], positive_text=pos,
                                negative_texts=negs[:max_negs]))
    console.print(f"Loaded {len(examples)} examples "
                  f"(skipped {skipped_pos} for empty positive, "
                  f"{skipped_neg} for <{max_negs} valid negatives)")
    return examples


class RerankerDataset(Dataset):
    def __init__(self, examples: list[Example], tokenizer, max_len: int = MAX_LEN):
        self.examples = examples
        self.tok = tokenizer
        self.max_len = max_len

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int):
        ex = self.examples[idx]
        pairs = [(ex.query, ex.positive_text)] + [(ex.query, n) for n in ex.negative_texts]
        encoded = self.tok(
            [q for q, _ in pairs],
            [d for _, d in pairs],
            padding="max_length",
            truncation=True,
            max_length=self.max_len,
            return_tensors="pt",
        )
        return {
            "input_ids": encoded["input_ids"],            # (1+N, L)
            "attention_mask": encoded["attention_mask"],  # (1+N, L)
        }


def collate(batch):
    # Just stack — each example already has shape (1+N, L)
    return {
        "input_ids": torch.stack([b["input_ids"] for b in batch]),       # (B, 1+N, L)
        "attention_mask": torch.stack([b["attention_mask"] for b in batch]),
    }


# ---------- training loop ----------

def compute_loss(model, batch, device) -> torch.Tensor:
    """Listwise InfoNCE: positive must outscore negatives for each query."""
    input_ids = batch["input_ids"].to(device)            # (B, 1+N, L)
    attn_mask = batch["attention_mask"].to(device)
    B, K, L = input_ids.shape
    out = model(input_ids=input_ids.view(B * K, L), attention_mask=attn_mask.view(B * K, L))
    scores = out.logits.view(B, K).squeeze(-1) if out.logits.dim() == 3 else out.logits.view(B, K)
    # positive is at index 0 for each row
    labels = torch.zeros(B, dtype=torch.long, device=device)
    return F.cross_entropy(scores, labels)


@torch.inference_mode()
def eval_accuracy(model, loader, device) -> float:
    """Fraction of queries where the positive scores higher than ALL negatives."""
    model.eval()
    correct = 0
    total = 0
    for batch in loader:
        input_ids = batch["input_ids"].to(device)
        attn_mask = batch["attention_mask"].to(device)
        B, K, L = input_ids.shape
        out = model(input_ids=input_ids.view(B * K, L), attention_mask=attn_mask.view(B * K, L))
        scores = out.logits.view(B, K).squeeze(-1) if out.logits.dim() == 3 else out.logits.view(B, K)
        # positive at idx 0; check it ranks first
        correct += (scores.argmax(dim=-1) == 0).sum().item()
        total += B
    model.train()
    return correct / max(total, 1)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--synth", type=Path, default=Path("data/eval/synth_queries.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("models/reranker-lora"))
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--max-negs", type=int, default=4, help="Cap negatives per query (mem-bound)")
    parser.add_argument("--eval-split", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    np.random.seed(args.seed)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    console.print(f"[bold]device:[/] {device}  [bold]dtype:[/] {dtype}")

    console.print(f"Loading tokenizer + base model: [cyan]{args.base}[/]")
    tokenizer = AutoTokenizer.from_pretrained(args.base)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.base, num_labels=1, torch_dtype=dtype,
    )
    model.to(device)

    # LoRA: target Q + V projections in attention (standard recipe for XLM-RoBERTa)
    lora_cfg = LoraConfig(
        task_type=TaskType.SEQ_CLS,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        target_modules=["query", "value"],
        bias="none",
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()
    model.train()

    examples = load_synth_dataset(args.synth, max_negs=args.max_negs)
    if not examples:
        console.print("[red]No usable examples. Did you run gen_synth_queries.py?[/]")
        return 1

    random.shuffle(examples)
    split = int(len(examples) * (1 - args.eval_split))
    train_examples, eval_examples = examples[:split], examples[split:]
    console.print(f"Train: {len(train_examples)}  Eval: {len(eval_examples)}")

    train_loader = DataLoader(
        RerankerDataset(train_examples, tokenizer), batch_size=args.batch,
        shuffle=True, collate_fn=collate,
    )
    eval_loader = DataLoader(
        RerankerDataset(eval_examples, tokenizer), batch_size=args.batch,
        shuffle=False, collate_fn=collate,
    )

    optim = torch.optim.AdamW(filter(lambda p: p.requires_grad, model.parameters()), lr=args.lr)

    baseline_acc = eval_accuracy(model, eval_loader, device)
    console.print(f"[yellow]Baseline eval accuracy (positive ranks first):[/] {baseline_acc:.3f}")

    history = {"baseline_acc": baseline_acc, "per_epoch": []}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        for epoch in range(args.epochs):
            task = progress.add_task(f"Epoch {epoch+1}/{args.epochs}", total=len(train_loader))
            losses: list[float] = []
            for batch in train_loader:
                optim.zero_grad()
                loss = compute_loss(model, batch, device)
                loss.backward()
                optim.step()
                losses.append(loss.item())
                progress.advance(task)
            mean_loss = sum(losses) / len(losses)
            acc = eval_accuracy(model, eval_loader, device)
            history["per_epoch"].append({"epoch": epoch + 1, "loss": mean_loss, "eval_acc": acc})
            console.print(f"[green]Epoch {epoch+1}[/]  loss={mean_loss:.4f}  eval_acc={acc:.3f}")

    args.out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(args.out)
    tokenizer.save_pretrained(args.out)
    (args.out / "training_history.json").write_text(json.dumps(history, indent=2))

    console.print(f"\n[bold green]Saved LoRA adapter -> {args.out}[/]")
    console.print(f"  baseline_acc={history['baseline_acc']:.3f}  "
                  f"final_acc={history['per_epoch'][-1]['eval_acc']:.3f}  "
                  f"delta={history['per_epoch'][-1]['eval_acc'] - history['baseline_acc']:+.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
