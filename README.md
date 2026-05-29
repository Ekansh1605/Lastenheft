# Lastenheft

> Sovereign multimodal RAG for the German industrial Mittelstand.
> Because Geschäftsgeheimnis doesn't belong in OpenAI's logs.

**Lastenheft** is the AI that reads every Lastenheft — and every datasheet, Schaltplan, Pflichtenheft, and SOP that came after. Multimodal retrieval over technical PDFs (engineering drawings, datasheets, BoMs, maintenance manuals) in German and English, designed from the ground up for EU AI Act compliance and on-premise sovereignty.

> 🚧 **Active build** — Day 1 of 5 complete (2026-05-28). README will be polished on Day 5 with final eval results, screenshots, and demo video.

---

## Why the name?

The **Lastenheft** (German engineering requirements specification) is the foundational document every German engineering project starts with. It defines what must be built, what constraints apply, what must be traceable. Every Bosch, Siemens, Trumpf, and ZF engineer has read a hundred of them.

This system is named after that document because it embodies the same values: **precision, traceability, accountability** — applied to AI over your industrial knowledge.

---

## Why this exists

German industrial Mittelstand companies have 40+ years of technical documentation locked in PDFs — engineering drawings, datasheets, maintenance manuals, certifications, BoMs — often mixed German + English, full of tables and diagrams that OCR mangles. They need AI to unlock this knowledge, but:

1. **They cannot send sensitive IP to OpenAI.** Sovereignty / Geschäftsgeheimnis concerns are non-negotiable.
2. **EU AI Act enforcement is active in 2026.** Industrial AI often classifies as high-risk under Article 6 (Annex I, safety components of machinery). Every deployment needs documented risk classification, transparency, and audit trails.
3. **They need engineering precision** — vibes-based LLM output is unacceptable when tolerances and certifications matter.
4. **Existing solutions (Microsoft Copilot, ChatGPT Enterprise) violate sovereignty requirements.**

Lastenheft is designed from the ground up for these constraints.

---

## Architecture

```
Next.js 15 frontend  ──►  FastAPI orchestration  ──►  LangGraph multi-agent
                                    │                  (planner / retriever /
                                    │                   validator / synthesizer)
                                    ▼
                          ┌─────────┴─────────┐
                          ▼                   ▼
              Multimodal retrieval     LLM Router
              (ColQwen2 / ColPali)     (local Qwen3 4B ↔ Claude/GPT)
              ▶ no OCR
              ▶ DE + EN
                          │                   │
                          ▼                   │
              Postgres + pgvector             │
                          │                   │
                          ▼                   ▼
              Audit log (EU AI Act Art. 13) + Compliance dashboard
```

### Key technical choices

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Frontend | Next.js 15 + Tailwind + shadcn | Modern, type-safe, fast |
| Auth + DB | Supabase + Postgres + pgvector | RLS-ready for multi-tenant |
| ML inference | FastAPI (Python 3.11) | Industry-standard ML serving |
| Visual retrieval | **ColQwen2** (ColPali fallback) | No OCR — handles diagrams, tables, technical drawings directly |
| Reranker | BGE-reranker-v2-m3, LoRA fine-tuned on DE+EN technical queries | Real ML signal, big quality lift |
| LLM (local) | **Qwen3 4B Instruct** via Ollama | Sovereign default, strong DE+EN, ~2.5GB VRAM |
| LLM (API) | Claude Sonnet 4.6 / GPT-4o | Opt-in for complex reasoning, logged per AI Act Art. 13 |
| Agents | LangGraph | Observable trajectories, production-grade |
| Observability | Self-hosted Langfuse | Full traces, no data leaves your infrastructure |
| Deploy | Docker Compose | One command: `docker compose up` |

---

## EU AI Act compliance — designed in, not bolted on

| Requirement | Implementation |
|-------------|----------------|
| Art. 6 — risk classification | System self-classifies as "limited risk" with documented reasoning (RAG over docs ≠ safety-critical decision-making). Seeded into `risk_classifications` table on first boot. |
| Art. 13 — transparency to users | Every answer shows: source citations, LLM provider used, confidence score, local-vs-API routing decision |
| Art. 14 — human oversight | All agent actions logged + reviewable; "Why this answer?" explanation modal |
| Art. 10 — data governance | Documented data sources, lineage from chunk back to source PDF + page + bbox |
| GDPR Art. 25 — privacy by design | Optional PII detector at ingest; full audit log; configurable data residency |
| GDPR Art. 17 — right to erasure | DELETE cascades from documents → embeddings → audit logs |

---

## Eval results

**Setup:** 26 industrial PDFs across 8 Mittelstand brands (Siemens, Festo, Bosch Rexroth, TRUMPF, KUKA, SICK, SEW Eurodrive + EU regulatory). 909 pages indexed via ColPali v1.3 multi-vector visual embeddings. 714 synthetic DE+EN technical query-passage pairs generated via Claude Sonnet 4.6, stratified across brands, with hard negatives mined via ColPali ANN. BGE-reranker-v2-m3 fine-tuned with LoRA (rank 16, ~2.6M trainable params, 0.46% of 570M base) for 3 epochs on 606 train / 108 held-out eval queries.

### Retrieval (full-corpus eval, 108 held-out queries, 909 candidate pages)

| Strategy | MRR | Hit@1 | Hit@5 | Hit@10 | nDCG@10 | median rank |
|----------|-----:|------:|------:|-------:|--------:|------------:|
| ColPali ANN only (baseline) | 0.341 | 20.4% | 45.4% | 61.1% | 0.395 | 3 |
| + BGE reranker (off-the-shelf) | 0.707 | 62.0% | 83.3% | 85.2% | 0.743 | 1 |
| + **BGE reranker (LoRA fine-tuned)** | **0.758** | **70.4%** | 82.4% | **85.2%** | **0.781** | **1** |

**LoRA fine-tune delta over off-the-shelf reranker: +5.1 pts MRR, +8.4 pts Hit@1, +3.8 pts nDCG@10.** The fine-tune learned to push the correct page to position 1 more confidently — exactly the property a citation-overlay UI cares about.

### In-training listwise accuracy (positive vs 4 hard negatives)

| Stage | Accuracy |
|-------|---------:|
| BGE-reranker-v2-m3 baseline | 0.843 |
| After epoch 1 | 0.889 |
| After epoch 2 | 0.861 |
| **After epoch 3 (saved)** | **0.898** |

### Reproducibility

```bash
# 1. Spin up infra
docker compose -f docker/docker-compose.yml --env-file .env up -d
uv sync

# 2. Download corpus + ingest
uv run python scripts/download_sample_pdfs.py
uv run python -m ml.ingest.cli ingest-dir data/pdfs

# 3. Generate synthetic training data (requires ANTHROPIC_API_KEY, ~$4)
uv run python -m ml.training.gen_synth_queries --sample 250 --hard-negs 5

# 4. Train reranker (1.5-2 hr on RTX 3060 6GB)
uv run python -m ml.training.train_reranker \
    --synth data/eval/synth_queries.jsonl \
    --epochs 3 --batch 4 --lr 2e-4 --max-negs 4

# 5. Evaluate (15 min)
uv run python -m ml.training.eval_retrieval --eval-split 0.15
```

Full results JSON: [`data/eval/retrieval_results.json`](data/eval/retrieval_results.json).
Training history: [`models/reranker-lora/training_history.json`](models/reranker-lora/training_history.json).

---

## Run locally

**Prerequisites:**
- Docker Desktop with WSL2
- Node.js 20+
- Python 3.11+ (via [uv](https://docs.astral.sh/uv/))
- ~12GB free disk (models + Postgres + container images)
- NVIDIA GPU with 6GB+ VRAM recommended (CPU fallback available, slower)

**Quick start:**

```bash
git clone https://github.com/Ekansh1605/lastenheft.git
cd lastenheft
cp .env.example .env       # add your API keys (Anthropic / OpenAI)
docker compose -f docker/docker-compose.yml up -d postgres langfuse-db langfuse
uv sync                     # installs Python deps (torch+CUDA, ColPali, LangGraph, ...)
uv run python scripts/prefetch_models.py    # downloads ColQwen2 (~6GB)
uv run python scripts/download_sample_pdfs.py
uv run python -m ml.ingest.cli ingest-dir data/pdfs
uvicorn api.main:app --reload
```

In a second terminal:
```bash
cd web && pnpm install && pnpm dev
```

Open http://localhost:3000.

---

## Curated demo corpus

26 publicly-available industrial documents from 8 major German Mittelstand brands. Mix of German + English. ~85 MB total.

| Brand | Domain | Docs |
|-------|--------|------|
| **Siemens SIMATIC** | Industrial automation / PLC | 7 (3 EN + 4 DE) |
| **Festo** | Pneumatics (ISO 15552 cylinders) | 5 (3 EN + 2 DE) |
| **SICK** | Industrial sensors (photoelectric, ultrasonic, laser) | 4 (EN) |
| **TRUMPF** | Laser / CNC machine tools | 3 (EN — TruLaser 1030 / 2030 + systems brochure) |
| **Bosch Rexroth** | Drives + hydraulic valves | 3 (EN — IndraDrive + directional + cartridge valves) |
| **KUKA** | Industrial robotics | 1 (EN — full robot portfolio, 27 MB / ~100+ pages) |
| **SEW Eurodrive** | Drives / Movigear | 1 (DE) |
| **EU regulatory** | AI Act + Machinery Regulation | 2 (EN — 2024/1689 + 2023/1230) |

URLs in [`scripts/download_sample_pdfs.py`](scripts/download_sample_pdfs.py). All sourced from publishers' public download portals — verified live May 2026.

---

## Limitations & future work

- **VRAM:** 6GB GPU shares VRAM between ColQwen2 and Qwen3 4B. Tight; works with quantization.
- **Reranker training data:** Synthetic queries from GPT-4o. Real customer query logs would improve recall on niche technical jargon.
- **PII detector:** Currently rule-based (Microsoft Presidio). A fine-tuned NER for German industrial PII would be next.
- **No SAP/MES integration yet.** Most Mittelstand have SAP — connector would be production deployment work.
- **Single-tenant in current MVP.** RLS schema is multi-tenant-ready; UI/billing is not.

---

## License

MIT — built as a portfolio piece by [Ekansh Sharma](https://github.com/Ekansh1605).
