"""
Retrieval service: query → ColQwen2 embed → ANN top-50 → late-interaction rerank → reranker → top-k.

For Day 1 we only do ANN. The late-interaction (MaxSim) rerank and BGE-reranker
join in on Day 2.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

from ml.ingest.embedder import embed_query
from ml.ingest.store import ann_search_pages

log = logging.getLogger("werkdocs.retrieval")


@dataclass(slots=True)
class RetrievedPage:
    page_id: str
    document_id: str
    filename: str
    page_number: int
    image_path: str
    score: float
    n_patches: int


def search(query: str, top_k: int = 10, ann_k: int = 50) -> list[RetrievedPage]:
    """Day 1 search: ANN only. Caller will layer reranking on Day 2."""
    q_vec = embed_query(query)
    candidates = ann_search_pages(q_vec, top_k=ann_k)
    candidates = candidates[:top_k]
    return [RetrievedPage(**c) for c in candidates]


def late_interaction_score(
    query_patches: np.ndarray,            # (n_q, 128)
    page_patches: np.ndarray,             # (n_p, 128)
) -> float:
    """ColBERT-style MaxSim: for each query token, take max similarity over page patches.
    Sum and you've got the late-interaction score. Better than mean-pool ANN but slower
    so we use it only for the top-50 ANN candidates."""
    sims = query_patches @ page_patches.T          # (n_q, n_p)
    return float(sims.max(axis=1).sum())
