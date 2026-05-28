"""
CLI for batch document ingestion.

Usage:
    uv run python -m ml.ingest.cli ingest-dir data/pdfs --source siemens-public
    uv run python -m ml.ingest.cli ingest-file data/pdfs/foo.pdf
    uv run python -m ml.ingest.cli stats
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from ml.ingest.embedder import embed_pages
from ml.ingest.pipeline import render_pdf
from ml.ingest.store import get_pool, upsert_document_and_pages

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(),
                    format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s")
log = logging.getLogger("werkdocs.cli")
console = Console()

app = typer.Typer(add_completion=False, help="WerkDocs ingestion CLI.")

PAGE_IMAGE_ROOT = Path(os.getenv("PAGE_IMAGE_ROOT", "data/cache/pages"))


@app.command("ingest-file")
def ingest_file(pdf_path: Path, source: str | None = None, language: str | None = None) -> None:
    """Ingest a single PDF: rasterize → embed → store."""
    if not pdf_path.exists():
        console.print(f"[red]File not found:[/] {pdf_path}")
        raise typer.Exit(1)
    _ingest_one(pdf_path, source=source, language=language)


@app.command("ingest-dir")
def ingest_dir(
    dir_path: Path,
    source: str | None = None,
    language: str | None = None,
    pattern: str = "*.pdf",
) -> None:
    """Ingest every PDF in a directory (non-recursive by default)."""
    if not dir_path.is_dir():
        console.print(f"[red]Not a directory:[/] {dir_path}")
        raise typer.Exit(1)
    pdfs = sorted(dir_path.glob(pattern))
    if not pdfs:
        console.print(f"[yellow]No PDFs matching {pattern} in {dir_path}[/]")
        raise typer.Exit(0)
    console.print(f"[bold]Found {len(pdfs)} PDFs[/]")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Ingesting", total=len(pdfs))
        for pdf in pdfs:
            try:
                _ingest_one(pdf, source=source, language=language, quiet=True)
            except Exception as e:  # noqa: BLE001
                log.error("Failed to ingest %s: %s", pdf.name, e)
            progress.advance(task)


@app.command("stats")
def stats() -> None:
    """Print row counts to verify the database state."""
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM documents")
        n_docs = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM pages")
        n_pages = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM page_embeddings")
        n_embs = cur.fetchone()[0]

    table = Table(title="WerkDocs index stats")
    table.add_column("Entity")
    table.add_column("Count", justify="right")
    table.add_row("documents", str(n_docs))
    table.add_row("pages", str(n_pages))
    table.add_row("page_embeddings", str(n_embs))
    console.print(table)


def _ingest_one(pdf_path: Path, source: str | None, language: str | None, quiet: bool = False) -> None:
    pdf_bytes = pdf_path.read_bytes()
    doc = render_pdf(pdf_bytes, filename=pdf_path.name)
    if not quiet:
        console.print(f"[cyan]{pdf_path.name}[/]: {doc.page_count} pages → embedding...")
    images = [p.image for p in doc.pages]
    embeddings = embed_pages(images, batch_size=1)
    doc_id = upsert_document_and_pages(
        doc=doc, embeddings=embeddings,
        page_image_root=PAGE_IMAGE_ROOT,
        source=source, language=language,
    )
    if not quiet:
        console.print(f"  → document_id=[bold]{doc_id}[/]")


if __name__ == "__main__":
    app()
