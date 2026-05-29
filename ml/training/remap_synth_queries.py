"""
After re-ingest, page UUIDs change but (filename, page_number) pairs remain
stable. This script rewrites synth_queries.jsonl so positives + negatives
reference the new page UUIDs. Saves regenerating ~$4 of synth queries.

Usage:
    uv run python -m ml.training.remap_synth_queries \
        --in  data/eval/synth_queries.jsonl \
        --out data/eval/synth_queries.remapped.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console

from ml.ingest.store import get_pool

log = logging.getLogger("remap")
console = Console()


def fetch_page_lookup() -> tuple[dict[tuple[str, int], str], dict[str, list[tuple[int, str]]]]:
    """
    Returns:
        by_filename_page : {(filename, page_number) -> page_uuid}
        by_filename      : {filename -> [(page_number, page_uuid), ...]}  used as fallback
    """
    by_filename_page: dict[tuple[str, int], str] = {}
    by_filename: dict[str, list[tuple[int, str]]] = {}
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.filename, p.page_number, p.id::text
            FROM pages p
            JOIN documents d ON d.id = p.document_id
            ORDER BY d.filename, p.page_number
            """
        )
        for filename, page_number, page_id in cur.fetchall():
            by_filename_page[(filename, page_number)] = page_id
            by_filename.setdefault(filename, []).append((page_number, page_id))
    return by_filename_page, by_filename


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="inp", type=Path, default=Path("data/eval/synth_queries.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("data/eval/synth_queries.remapped.jsonl"))
    args = parser.parse_args()

    by_fp, by_f = fetch_page_lookup()
    console.print(f"[bold]Loaded[/] {len(by_fp)} pages across {len(by_f)} documents from DB")

    records: list[dict] = []
    with args.inp.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    console.print(f"[bold]Loaded[/] {len(records)} input records")

    # Build old_page_id -> (filename, page_number) lookup from the input file itself
    # (the synth records carry positive_filename + positive_page_number; negatives don't,
    # so we'll need a second pass to resolve negatives via stored info)
    old_id_to_fp: dict[str, tuple[str, int]] = {}
    for r in records:
        old_id_to_fp[r["positive_page_id"]] = (r["positive_filename"], r["positive_page_number"])

    # For negatives, we don't have filename/page in the synth record. We need to look them up
    # from the OLD DB. Since we just truncated, that's gone. So we MUST drop negatives that
    # we can't map by directly resolving via the old UUIDs (which no longer exist).
    # Solution: re-mine hard negatives via ANN on the NEW corpus (cheap, no API call).
    from ml.ingest.embedder import embed_query

    def mine_negs(query: str, positive_id: str, k: int = 5) -> list[str]:
        q_vec = embed_query(query)
        with get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT pe.page_id::text
                FROM page_embeddings pe
                WHERE pe.page_id::text <> %s
                ORDER BY pe.mean_vector <=> %s::vector
                LIMIT %s
                """,
                (positive_id, q_vec.tolist(), k),
            )
            return [r[0] for r in cur.fetchall()]

    written = 0
    missing_positive = 0
    with args.out.open("w", encoding="utf-8") as fp:
        for r in records:
            fname = r["positive_filename"]
            pnum = r["positive_page_number"]
            new_pos = by_fp.get((fname, pnum))
            if not new_pos:
                missing_positive += 1
                continue
            try:
                new_negs = mine_negs(r["query"], new_pos, k=len(r.get("negative_page_ids", [])) or 5)
            except Exception as e:  # noqa: BLE001
                log.warning("Neg mining failed for query '%s': %s", r["query"][:60], e)
                new_negs = []
            if not new_negs:
                continue
            new_record = {
                **r,
                "positive_page_id": new_pos,
                "negative_page_ids": new_negs,
            }
            fp.write(json.dumps(new_record, ensure_ascii=False) + "\n")
            written += 1

    console.print(f"\n[bold green]Wrote {written}[/] records -> {args.out} "
                  f"(skipped {missing_positive} for missing positive page)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
