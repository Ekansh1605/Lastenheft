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

# Curated list of public industrial PDFs. URLs verified live via WebSearch May 2026.
# If any URL fails on your machine, the script just skips it — no hard failure.
SOURCES: list[dict[str, str]] = [
    # ---- Siemens SIMATIC S7-1200 (English) ----
    {"name": "siemens-s7-1200-system-manual-en.pdf",
     "url": "https://support.industry.siemens.com/cs/attachments/109797241/s71200_system_manual_en-US_en-US.pdf",
     "source": "siemens-simatic-s7-1200"},
    {"name": "siemens-s7-1200-g2-system-manual-en.pdf",
     "url": "https://support.industry.siemens.com/cs/attachments/109972011/S71200_G2_system_manual_en-US.pdf",
     "source": "siemens-simatic-s7-1200"},
    {"name": "siemens-s7-1200-functional-safety-en.pdf",
     "url": "https://support.industry.siemens.com/cs/attachments/104547552/s71200_f_user_manual_en-US_en-US.pdf",
     "source": "siemens-simatic-s7-1200"},

    # ---- Siemens SIMATIC S7-1500 (German — bilingual demo) ----
    {"name": "siemens-s7-1500-cpu1517-pndp-de.pdf",
     "url": "https://cache.industry.siemens.com/dl/files/765/90471765/att_895905/v2/s71500_cpu1517_3_pndp_manual_de-DE_de-DE.pdf",
     "source": "siemens-simatic-s7-1500"},
    {"name": "siemens-s7-1500-cpu1518-pndp-de.pdf",
     "url": "https://cache.industry.siemens.com/dl/files/632/81164632/att_895909/v2/s71500_cpu1518_4_pndp_manual_de-DE_de-DE.pdf",
     "source": "siemens-simatic-s7-1500"},
    {"name": "siemens-s7-1500-di-16x230vac-de.pdf",
     "url": "https://cache.industry.siemens.com/dl/files/398/59193398/att_77122/v1/s71500_di_16x230vac_ba_manual_de-DE_de-DE.pdf",
     "source": "siemens-simatic-s7-1500"},
    {"name": "siemens-hmi-lite-systemhandbuch-de.pdf",
     "url": "https://cache.industry.siemens.com/dl/files/639/109823639/att_1152244/v1/Systemhandbuch_HMILite_V18_DE.pdf",
     "source": "siemens-hmi"},

    # ---- Bosch Rexroth (drives + automation) ----
    {"name": "bosch-rexroth-indradrive-cs-datasheet-en.pdf",
     "url": "https://www.cmafh.com/images/Master%20PDFs/BRC/Drives/Rexroth%20CS%20Drive%20Data%20Sheet%20p146994_en.pdf",
     "source": "bosch-rexroth"},

    # ---- Festo (pneumatics — DE + EN, ISO 15552) ----
    {"name": "festo-dnc-cylinder-en.pdf",
     "url": "https://www.festo.com/media/catalog/202856_documentation.pdf",
     "source": "festo-pneumatics"},
    {"name": "festo-dsbc-cylinder-en.pdf",
     "url": "https://www.festo.com/media/catalog/202904_documentation.pdf",
     "source": "festo-pneumatics"},
    {"name": "festo-adn-aen-compact-cylinder-en.pdf",
     "url": "https://www.festo.com/media/catalog/202551_documentation.pdf",
     "source": "festo-pneumatics"},
    {"name": "festo-dsbc-normzylinder-de.pdf",
     "url": "https://ftp.festo.com/public/pneumatic/SOFTWARE_SERVICE/Documentation/2017/DE/DSBC_DE.PDF",
     "source": "festo-pneumatics"},
    {"name": "festo-dsbc-cylinder-2023-en.pdf",
     "url": "https://ftp.festo.com/Public/PNEUMATIC/SOFTWARE_SERVICE/Documentation/2023/EN/DSBC_EN.PDF",
     "source": "festo-pneumatics"},

    # ---- EU regulatory (already-working) ----
    {"name": "eu-machinery-regulation-2023-1230.pdf",
     "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32023R1230",
     "source": "eu-regulation"},
    {"name": "eu-ai-act-2024-1689.pdf",
     "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32024R1689",
     "source": "eu-ai-act"},
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
