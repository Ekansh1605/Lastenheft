"""
ColQwen2 multi-vector visual embedder.

Loads once (model is ~5GB FP16). Use process-level singleton — never load twice.
Falls back to ColPali if ColQwen2 isn't available or VRAM is tight.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import torch
from PIL import Image

log = logging.getLogger("lastenheft.embed")


@dataclass(slots=True)
class EmbeddingResult:
    model: str
    mean_vector: np.ndarray        # (128,) float32
    patch_vectors: np.ndarray      # (n_patches, 128) float32
    n_patches: int


def _device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


@lru_cache(maxsize=1)
def _load_model():
    """Load ColQwen2 (preferred) or ColPali (fallback). Cached for process lifetime."""
    from colpali_engine.models import ColPali, ColPaliProcessor, ColQwen2, ColQwen2Processor

    device = _device()
    dtype = torch.bfloat16 if device == "cuda" else torch.float32

    primary = os.getenv("COLQWEN_MODEL", "vidore/colqwen2-v1.0")
    fallback = os.getenv("COLPALI_FALLBACK", "vidore/colpali-v1.3")

    for name, model_cls, proc_cls in [
        (primary, ColQwen2, ColQwen2Processor),
        (fallback, ColPali, ColPaliProcessor),
    ]:
        try:
            log.info("Loading visual embedder: %s (device=%s dtype=%s)", name, device, dtype)
            model = model_cls.from_pretrained(name, torch_dtype=dtype, device_map=device).eval()
            processor = proc_cls.from_pretrained(name)
            log.info("Visual embedder ready: %s", name)
            return model, processor, name
        except Exception as e:  # noqa: BLE001 — try fallback on any load failure
            log.warning("Failed to load %s: %s — trying fallback", name, e)
    raise RuntimeError("Could not load any visual embedder (ColQwen2 nor ColPali)")


@torch.inference_mode()
def embed_pages(images: list[Image.Image], batch_size: int = 1) -> list[EmbeddingResult]:
    """Embed a list of page images. Small batch_size on 6GB VRAM."""
    model, processor, model_name = _load_model()
    out: list[EmbeddingResult] = []
    for i in range(0, len(images), batch_size):
        batch = images[i : i + batch_size]
        inputs = processor.process_images(batch).to(model.device)
        embeds = model(**inputs)               # (B, n_patches, 128) bfloat16/float32
        embeds_np = embeds.float().cpu().numpy()
        for patches in embeds_np:
            mean = patches.mean(axis=0)
            # L2-normalize for cosine ANN
            mean = mean / (np.linalg.norm(mean) + 1e-12)
            out.append(EmbeddingResult(
                model=model_name,
                mean_vector=mean.astype(np.float32),
                patch_vectors=patches.astype(np.float32),
                n_patches=patches.shape[0],
            ))
    return out


@torch.inference_mode()
def embed_query(query: str) -> np.ndarray:
    """Embed a text query, return mean-pooled 128-d vector for ANN."""
    model, processor, _ = _load_model()
    inputs = processor.process_queries([query]).to(model.device)
    embeds = model(**inputs)                   # (1, n_tokens, 128)
    patches = embeds[0].float().cpu().numpy()
    mean = patches.mean(axis=0)
    return (mean / (np.linalg.norm(mean) + 1e-12)).astype(np.float32)
