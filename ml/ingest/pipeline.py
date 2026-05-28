"""
PDF ingestion pipeline.

Flow per document:
    1. Hash the PDF (sha256) so we de-dupe across uploads.
    2. Rasterize each page to PNG via pypdfium2 (faster + pure-Python than pdf2image).
    3. Extract page text via pypdfium2 textpage (used downstream for synthetic
       query generation, RAGAS faithfulness scoring, etc.).
    4. Compute ColPali multi-vector embeddings per page (see embedder.py).
    5. Mean-pool each page's patches into a single 128-dim vector for ANN.
    6. Persist documents/pages/page_embeddings rows.

This is the hot path. Performance matters because we'll index ~25 PDFs.
"""

from __future__ import annotations

import hashlib
import io
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
from PIL import Image

log = logging.getLogger("lastenheft.ingest")

RENDER_DPI = int(os.getenv("INGEST_DPI", "150"))   # 150 is the ColPali default
MAX_PAGES_PER_DOC = int(os.getenv("INGEST_MAX_PAGES", "50"))


@dataclass(slots=True)
class RenderedPage:
    page_number: int
    image: Image.Image
    width: int
    height: int
    text: str          # extractable text (may be empty for scanned/image-only pages)


@dataclass(slots=True)
class IngestedDocument:
    sha256: str
    filename: str
    page_count: int
    pages: list[RenderedPage]


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _extract_text(page: pdfium.PdfPage) -> str:
    """Pull whatever text pypdfium2 can extract from a page. Empty string if none."""
    try:
        textpage = page.get_textpage()
        text = textpage.get_text_range() or ""
        textpage.close()
        return text.strip()
    except Exception as e:  # noqa: BLE001 — text extraction is best-effort
        log.debug("Text extraction failed on page: %s", e)
        return ""


def render_pdf(pdf_bytes: bytes, filename: str) -> IngestedDocument:
    """Rasterize a PDF's pages to PIL images at INGEST_DPI, also extract text."""
    pdf = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
    page_count = len(pdf)
    if page_count > MAX_PAGES_PER_DOC:
        log.warning("Document %s has %d pages, capping at %d", filename, page_count, MAX_PAGES_PER_DOC)

    scale = RENDER_DPI / 72.0
    pages: list[RenderedPage] = []
    for idx in range(min(page_count, MAX_PAGES_PER_DOC)):
        page = pdf[idx]
        bitmap = page.render(scale=scale)
        img = bitmap.to_pil().convert("RGB")
        text = _extract_text(page)
        pages.append(RenderedPage(
            page_number=idx + 1,
            image=img,
            width=img.width,
            height=img.height,
            text=text,
        ))
        page.close()
    pdf.close()
    return IngestedDocument(
        sha256=sha256_bytes(pdf_bytes),
        filename=filename,
        page_count=len(pages),
        pages=pages,
    )


def save_page_image(image: Image.Image, doc_sha: str, page_number: int, root: Path) -> Path:
    """Persist the rendered page as PNG. Path is stable for re-runs."""
    doc_dir = root / doc_sha
    doc_dir.mkdir(parents=True, exist_ok=True)
    out = doc_dir / f"page-{page_number:04d}.png"
    if not out.exists():
        image.save(out, format="PNG", optimize=True)
    return out


def pack_patch_vectors(patches: np.ndarray) -> bytes:
    """Pack [n_patches, 128] float32 patches as float16 bytes for compact DB storage."""
    if patches.dtype != np.float16:
        patches = patches.astype(np.float16)
    return patches.tobytes()


def unpack_patch_vectors(blob: bytes, n_patches: int, dim: int = 128) -> np.ndarray:
    arr = np.frombuffer(blob, dtype=np.float16).reshape(n_patches, dim)
    return arr.astype(np.float32)
