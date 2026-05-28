"""
Pre-download the visual embedder weights so first ingest is instant.

ColQwen2 is ~5-6GB. Doing this explicitly (vs on-demand) so the download is
visible and won't kill ingest UX.
"""

from __future__ import annotations

import logging
import os
import sys
import time

import torch

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s")
log = logging.getLogger("prefetch")


def main() -> int:
    primary = os.getenv("COLQWEN_MODEL", "vidore/colqwen2-v1.0")
    fallback = os.getenv("COLPALI_FALLBACK", "vidore/colpali-v1.3")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    log.info("device=%s dtype=%s", device, dtype)

    from colpali_engine.models import ColPali, ColPaliProcessor, ColQwen2, ColQwen2Processor

    for name, model_cls, proc_cls in [
        (primary, ColQwen2, ColQwen2Processor),
        (fallback, ColPali, ColPaliProcessor),
    ]:
        log.info("Downloading + loading %s ...", name)
        t0 = time.time()
        try:
            model = model_cls.from_pretrained(name, torch_dtype=dtype, device_map=device).eval()
            processor = proc_cls.from_pretrained(name)
            took = time.time() - t0
            log.info("OK   %s  (%.1fs)", name, took)
            if device == "cuda":
                used = torch.cuda.memory_allocated() / 1e9
                log.info("   VRAM in use after load: %.2f GB", used)
            # Free immediately so we can try the next one
            del model, processor
            if device == "cuda":
                torch.cuda.empty_cache()
        except Exception as e:  # noqa: BLE001
            log.error("FAIL %s : %s", name, e)
            if name == primary:
                log.warning("ColQwen2 failed - we'll keep weights for ColPali fallback only")
            else:
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
