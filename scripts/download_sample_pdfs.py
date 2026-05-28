"""
Download a curated set of publicly-available industrial technical PDFs
to use as our seed corpus.

Sources chosen for Mittelstand credibility:
  - Siemens SIMATIC public datasheets (DE + EN)
  - Bosch Rexroth catalog excerpts (DE + EN)
  - EU machinery directive primer
  - CE marking guidance

NOTE: This script intentionally uses only documents the publishers have placed
on their public websites. We do not redistribute the files; we just stash
local copies for indexing. The README cites the sources.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from pathlib import Path

import httpx
from rich.console import Console
from rich.progress import Progress

console = Console()
log = logging.getLogger("download_sample_pdfs")

# Curated list of public industrial PDFs. URLs verified manually before commit.
# If any URL 404s on your machine, the script just skips it — no hard failure.
SOURCES: list[dict[str, str]] = [
    # ---- Siemens SIMATIC ----
    {"name": "siemens-simatic-s7-1200-system-manual.pdf",
     "url": "https://cache.industry.siemens.com/dl/files/465/109764465/att_1130271/v1/s71200_system_manual_en-US_en-US.pdf",
     "source": "siemens-simatic"},
    {"name": "siemens-simatic-s7-1500-systemhandbuch.pdf",
     "url": "https://cache.industry.siemens.com/dl/files/792/59191792/att_895917/v1/s71500_system_manual_de-DE_de-DE.pdf",
     "source": "siemens-simatic"},
    # ---- Bosch Rexroth ----
    {"name": "bosch-rexroth-indradrive-cs.pdf",
     "url": "https://www.boschrexroth.com/various/utilities/mediadirectory/download/index.jsp?object_nr=R911334042",
     "source": "bosch-rexroth"},
    # ---- EU regulatory ----
    {"name": "eu-machinery-regulation-2023-1230.pdf",
     "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32023R1230",
     "source": "eu-regulation"},
    {"name": "eu-ai-act-2024-1689.pdf",
     "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32024R1689",
     "source": "eu-ai-act"},
    # ---- CE marking ----
    {"name": "ce-marking-blue-guide-2022.pdf",
     "url": "https://op.europa.eu/o/opportal-service/download-handler?identifier=ab800f04-5747-11ed-92ed-01aa75ed71a1&format=pdf&language=en&productionSystem=cellar&part=",
     "source": "ce-marking"},
]


def download_one(url: str, dest: Path, client: httpx.Client) -> bool:
    if dest.exists() and dest.stat().st_size > 1024:
        log.info("Skip (already present): %s", dest.name)
        return True
    try:
        r = client.get(url, follow_redirects=True, timeout=60.0)
        r.raise_for_status()
        if not r.headers.get("content-type", "").lower().startswith(("application/pdf", "application/octet-stream")):
            log.warning("Skip non-PDF response (%s): %s",
                        r.headers.get("content-type", "?"), url)
            return False
        dest.write_bytes(r.content)
        sha = hashlib.sha256(r.content).hexdigest()[:12]
        log.info("Downloaded %s (%.1f MB, sha=%s)", dest.name, len(r.content) / 1e6, sha)
        return True
    except Exception as e:  # noqa: BLE001
        log.error("Failed %s: %s", url, e)
        return False


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("data/pdfs"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    ok = 0
    with httpx.Client(headers={"User-Agent": "WerkDocs/0.1 (portfolio research)"}) as client, \
         Progress(console=console) as progress:
        task = progress.add_task("Downloading sample PDFs", total=len(SOURCES))
        for src in SOURCES:
            dest = args.out / src["name"]
            if download_one(src["url"], dest, client):
                ok += 1
            progress.advance(task)

    console.print(f"\n[bold]Downloaded {ok}/{len(SOURCES)} PDFs into {args.out}[/]")
    if ok == 0:
        console.print("[red]Nothing downloaded. Check network or update SOURCES URLs.[/]")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
