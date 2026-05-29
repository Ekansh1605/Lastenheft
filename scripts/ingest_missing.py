"""
Ingest only PDFs in data/pdfs/ that aren't yet in the documents table.
Used to recover from a partial ingest (e.g., Windows auto-update reboot).
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console

from ml.ingest.cli import _ingest_one, PAGE_IMAGE_ROOT  # noqa: F401
from ml.ingest.store import get_pool

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
)
console = Console()


def existing_filenames() -> set[str]:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT filename FROM documents")
        return {row[0] for row in cur.fetchall()}


def main() -> int:
    pdf_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "data/pdfs")
    all_pdfs = sorted(pdf_dir.glob("*.pdf"))
    have = existing_filenames()
    missing = [p for p in all_pdfs if p.name not in have]

    console.print(f"[bold]All PDFs:[/] {len(all_pdfs)} | [bold]In DB:[/] {len(have)} | [bold]Missing:[/] {len(missing)}")
    if not missing:
        console.print("[green]Nothing to do.[/]")
        return 0
    console.print("Missing:")
    for p in missing:
        console.print(f"  {p.name}")

    for i, p in enumerate(missing, 1):
        console.print(f"\n[cyan]({i}/{len(missing)}) {p.name}[/]")
        try:
            _ingest_one(p, source=None, language=None, quiet=True)
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]  FAILED: {e}[/]")
            continue
    return 0


if __name__ == "__main__":
    sys.exit(main())
