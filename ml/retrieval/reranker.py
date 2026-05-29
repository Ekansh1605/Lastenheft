"""
BGE cross-encoder reranker with LoRA adapter, loaded once per process.

Used by the agent retriever node + eval scripts. Singleton via lru_cache
so loading the 568M base model + LoRA happens at most once.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForSequenceClassification, AutoTokenizer

log = logging.getLogger("lastenheft.rerank")

DEFAULT_BASE = "BAAI/bge-reranker-v2-m3"
DEFAULT_LORA = "models/reranker-lora"


def _device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


@lru_cache(maxsize=1)
def _load() -> tuple[AutoTokenizer, torch.nn.Module, str]:
    base = os.getenv("RERANKER_BASE", DEFAULT_BASE)
    lora_path = Path(os.getenv("RERANKER_LORA", DEFAULT_LORA))
    device = _device()
    dtype = torch.bfloat16 if device == "cuda" else torch.float32

    log.info("loading reranker base=%s lora=%s device=%s", base, lora_path, device)
    tok = AutoTokenizer.from_pretrained(base)
    model = AutoModelForSequenceClassification.from_pretrained(
        base, num_labels=1, torch_dtype=dtype,
    )
    label = base
    if lora_path.exists():
        model = PeftModel.from_pretrained(model, str(lora_path))
        label = f"{base}+lora"
        log.info("loaded LoRA adapter from %s", lora_path)
    else:
        log.warning("no LoRA adapter at %s, using base reranker only", lora_path)
    model = model.to(device).eval()
    return tok, model, label


@torch.inference_mode()
def rerank(query: str, passages: list[str], top_k: int = 5,
           batch_size: int = 16) -> list[tuple[int, float]]:
    """Score (query, passage) pairs. Returns list of (passage_index, score) sorted desc.

    Cap output at top_k. Indices map back to the caller's `passages` list.
    """
    if not passages:
        return []
    tok, model, _ = _load()
    device = next(model.parameters()).device

    scores: list[float] = []
    for i in range(0, len(passages), batch_size):
        chunk = passages[i : i + batch_size]
        enc = tok([query] * len(chunk), chunk, padding=True, truncation=True,
                  max_length=512, return_tensors="pt").to(device)
        out = model(**enc)
        logit = out.logits.squeeze(-1) if out.logits.dim() == 2 else out.logits
        scores.extend(logit.float().cpu().tolist())

    indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    return indexed[:top_k]


def model_label() -> str:
    """Identifier of which reranker is loaded — used in audit log."""
    _tok, _model, label = _load()
    return label
