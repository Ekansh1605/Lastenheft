"""Quick sanity check on retrieval. Run after at least one PDF is ingested."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.table import Table

os.environ.setdefault("DATABASE_URL", "postgresql://lastenheft:lastenheft@localhost:5433/lastenheft")

from ml.retrieval.search import search  # noqa: E402

console = Console()


def main(query: str = "What is the operating voltage range?") -> int:
    console.print(f"[bold]Query:[/] {query}")
    hits = search(query, top_k=5, ann_k=20)
    if not hits:
        console.print("[red]No hits.[/]")
        return 1
    t = Table(title=f"Top {len(hits)} pages")
    t.add_column("rank")
    t.add_column("filename")
    t.add_column("page", justify="right")
    t.add_column("score", justify="right")
    for i, h in enumerate(hits, 1):
        t.add_row(str(i), h.filename, str(h.page_number), f"{h.score:.4f}")
    console.print(t)
    return 0


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "What is the operating voltage range?"
    sys.exit(main(q))
