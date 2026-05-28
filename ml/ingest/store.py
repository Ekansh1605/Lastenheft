"""
Postgres persistence for documents, pages, and page_embeddings.

Uses psycopg3 with the connection pool. We open the pool lazily so importing
this module doesn't crash when Postgres isn't running yet.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import psycopg
from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

from ml.ingest.embedder import EmbeddingResult
from ml.ingest.pipeline import IngestedDocument, pack_patch_vectors, save_page_image

log = logging.getLogger("werkdocs.store")

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        url = os.getenv("DATABASE_URL", "postgresql://werkdocs:werkdocs@localhost:5432/werkdocs")
        _pool = ConnectionPool(url, min_size=1, max_size=4, configure=_configure_conn)
    return _pool


def _configure_conn(conn: psycopg.Connection) -> None:
    register_vector(conn)


def upsert_document_and_pages(
    doc: IngestedDocument,
    embeddings: list[EmbeddingResult],
    page_image_root: Path,
    source: str | None = None,
    language: str | None = None,
) -> str:
    """Persist a fully-ingested document. Returns the document UUID as a string."""
    assert len(embeddings) == doc.page_count, "embedding count must match page count"

    with get_pool().connection() as conn, conn.cursor() as cur:
        # Insert document (idempotent on sha256)
        cur.execute(
            """
            INSERT INTO documents (filename, sha256, page_count, language, source, indexed_at)
            VALUES (%s, %s, %s, %s, %s, now())
            ON CONFLICT (sha256) DO UPDATE
                SET indexed_at = EXCLUDED.indexed_at
            RETURNING id::text
            """,
            (doc.filename, doc.sha256, doc.page_count, language, source),
        )
        document_id = cur.fetchone()[0]

        for page, emb in zip(doc.pages, embeddings, strict=True):
            image_path = save_page_image(page.image, doc.sha256, page.page_number, page_image_root)

            cur.execute(
                """
                INSERT INTO pages (document_id, page_number, width, height, image_path)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (document_id, page_number) DO UPDATE
                    SET image_path = EXCLUDED.image_path
                RETURNING id::text
                """,
                (document_id, page.page_number, page.width, page.height, str(image_path)),
            )
            page_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO page_embeddings (page_id, model, mean_vector, patch_vectors, n_patches)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (page_id) DO UPDATE
                    SET model = EXCLUDED.model,
                        mean_vector = EXCLUDED.mean_vector,
                        patch_vectors = EXCLUDED.patch_vectors,
                        n_patches = EXCLUDED.n_patches
                """,
                (page_id, emb.model, emb.mean_vector, pack_patch_vectors(emb.patch_vectors), emb.n_patches),
            )

        conn.commit()
    log.info("Ingested doc %s (%d pages) → %s", doc.filename, doc.page_count, document_id)
    return document_id


def ann_search_pages(query_vector: Any, top_k: int = 50) -> list[dict[str, Any]]:
    """Top-k ANN over mean_vectors. Returns rows with document/page metadata + score."""
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                pe.page_id::text,
                p.document_id::text,
                d.filename,
                p.page_number,
                p.image_path,
                1 - (pe.mean_vector <=> %s::vector) AS score,
                pe.n_patches
            FROM page_embeddings pe
            JOIN pages p ON p.id = pe.page_id
            JOIN documents d ON d.id = p.document_id
            ORDER BY pe.mean_vector <=> %s::vector
            LIMIT %s
            """,
            (query_vector.tolist(), query_vector.tolist(), top_k),
        )
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
