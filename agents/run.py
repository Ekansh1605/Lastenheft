"""
CLI for running the agent end-to-end. Useful for testing and demos.

Usage:
    uv run python -m agents.run "What is the operating voltage of the IndraDrive Cs?"
    uv run python -m agents.run --mode local-only "Welche Schutzart hat das DSBC?"
    uv run python -m agents.run --json "What is the max sheet thickness for the TruLaser 2030?"
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agents.graph import get_graph

console = Console()


def main() -> int:
    logging.basicConfig(level="INFO",
                        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="+", help="Query to ask")
    parser.add_argument("--mode", choices=["local-only", "hybrid", "api-only"],
                        default="hybrid")
    parser.add_argument("--json", action="store_true", help="Print raw JSON only")
    args = parser.parse_args()
    query = " ".join(args.query)

    graph = get_graph()
    initial = {
        "query": query,
        "sovereignty_mode": args.mode,
        "trace": [],
    }

    if args.json:
        result = graph.invoke(initial)
        print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
        return 0

    console.print(Panel.fit(f"[bold]Q:[/] {query}\n[dim]mode={args.mode}[/]",
                            border_style="cyan"))

    result = graph.invoke(initial)

    # Trace
    t = Table(title="Agent trace")
    t.add_column("step", style="cyan")
    t.add_column("detail")
    t.add_column("ms", justify="right", style="dim")
    for ev in result.get("trace", []):
        t.add_row(ev["step"], ev["detail"], str(ev["latency_ms"]))
    console.print(t)

    # Citations
    ct = Table(title="Citations")
    ct.add_column("rank", justify="right")
    ct.add_column("filename")
    ct.add_column("page", justify="right")
    ct.add_column("score", justify="right")
    for i, c in enumerate(result.get("retrieved") or [], 1):
        ct.add_row(str(i), c["filename"], str(c["page_number"]), f"{c['score']:.3f}")
    console.print(ct)

    # Answer
    answer = result.get("answer", "(no answer)")
    provider = result.get("llm_provider", "?")
    model = result.get("llm_model", "?")
    cost = result.get("cost_usd", 0.0)
    console.print(Panel(answer,
                        title=f"[bold]Answer  [dim]({provider} / {model}, ${cost:.4f})[/]",
                        border_style="green"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
