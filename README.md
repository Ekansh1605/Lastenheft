# Lastenheft

> Sovereign multimodal RAG for the German industrial Mittelstand.
> Because Geschäftsgeheimnis doesn't belong in OpenAI's logs.

**Lastenheft** is a production-grade Q&A system over technical PDFs from German industrial manufacturers (Siemens, Bosch Rexroth, TRUMPF, KUKA, Festo, SICK, SEW Eurodrive) — handling engineering drawings, datasheets, BoMs, and maintenance manuals in German + English without OCR, without sending IP to OpenAI, and with EU AI Act compliance designed in from the schema layer up.

Named after the *Lastenheft* — the customer requirements specification document every German engineer at Bosch / Siemens / Trumpf / ZF starts a project with.

---

## Why this exists

German industrial Mittelstand has 40+ years of technical documentation locked in PDFs. They need AI to unlock it, but:

1. **They cannot send sensitive IP to OpenAI.** Geschäftsgeheimnis is non-negotiable.
2. **EU AI Act enforcement is active in 2026.** Industrial AI often classifies as high-risk under Article 6; every deployment needs documented risk classification, transparency, audit trails.
3. **They need engineering precision** — vibes-based LLM output fails when tolerances and certifications matter.
4. **Existing solutions (Microsoft Copilot for M365, ChatGPT Enterprise) violate sovereignty requirements.**

Lastenheft solves all four.

---

## What it does (~3 minute demo)

> _Demo video and screenshots coming — see [DEMO.md](DEMO.md) for the script and recorded walkthrough_

**A user asks an industrial question in German or English** →
the multi-agent system decomposes it →
**ColPali multimodal retrieval** finds the relevant pages (without OCR — works on diagrams, tables, technical drawings) →
**a LoRA-fine-tuned BGE reranker** picks the top 5 →
**a local Qwen3 4B model OR an opt-in API LLM** writes the answer with bracketed citations →
**every step writes an audit row** for EU AI Act Article 13 transparency.

The user sees the live agent trajectory, a cited answer, the citation cards, and can replay any past query from the sidebar history.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│ Next.js 15 frontend                                                  │
│  • Sidebar with query history (ChatGPT-style)                        │
│  • SSE-streamed agent trajectory timeline                            │
│  • Citation pills [1] [2] anchored to source cards                   │
│  • Live AI-Act compliance dashboard                                  │
└─────────────────────────────────┬────────────────────────────────────┘
                                  │ POST /query/stream (SSE)
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│ FastAPI orchestration                                                │
│  • slowapi per-IP rate limit (configurable)                          │
│  • asyncio.wait_for hard timeout                                     │
│  • request.is_disconnected() cancellation                            │
│  • CORS via CORS_ORIGINS env var                                     │
└─────────────────────────────────┬────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│ LangGraph multi-agent (agents/)                                      │
│                                                                      │
│   planner ─► retriever ─► validator ─► synthesizer                   │
│      │           │            │             │                        │
│      │           │            │             ▼                        │
│      │           │            │     ┌──────────────┐                 │
│      │           │            │     │ LLM Router   │                 │
│      │           │            │     │   • local    │                 │
│      │           │            │     │     Qwen3 4B │                 │
│      │           │            │     │   • API      │                 │
│      │           │            │     │     Claude   │                 │
│      │           │            │     │   • fallback │                 │
│      │           │            │     │     on error │                 │
│      │           │            │     └──────────────┘                 │
│      │           │            │                                      │
│      │           ▼            └─► coverage + escalation              │
│      │   ColPali v1.3 (no OCR, multi-vector)                         │
│      │       → mean-vector ANN over pgvector                         │
│      │       → BGE-reranker-v2-m3 + LoRA (+8.4 Hit@1)                │
│      ▼                                                               │
│   decompose sub-queries, score complexity                            │
└─────────────────────────────────┬────────────────────────────────────┘
                                  │
                ┌─────────────────┼─────────────────┐
                ▼                 ▼                 ▼
        ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
        │   Postgres   │  │   audit_     │  │   Langfuse   │
        │  + pgvector  │  │   events     │  │   (optional) │
        │              │  │              │  │              │
        │  • documents │  │  Art. 13     │  │  trace UI    │
        │  • pages     │  │  per-node    │  │              │
        │  • embeddings│  │  provider/   │  │              │
        │              │  │  model/cost  │  │              │
        └──────────────┘  └──────────────┘  └──────────────┘
```

### Tech choices

| Layer | Choice | Why |
|-------|--------|-----|
| Frontend | Next.js 16 + React 19 + Tailwind v4 + TypeScript | Modern, type-safe, App Router with SSE |
| Backend | FastAPI 0.115 (Python 3.11) | Async, fast, OpenAPI for free, slowapi rate limiting |
| DB | Postgres 16 + pgvector 0.8 + HNSW | ANN at scale, RLS-ready for multi-tenant |
| Visual retrieval | **ColPali v1.3** (PaliGemma-based) | No OCR — embeds page IMAGES directly. Handles diagrams, tables, drawings that text retrievers miss. |
| Reranker | BGE-reranker-v2-m3 (568M) + LoRA (~2.6M trainable) | Cross-encoder for high-precision top-K; LoRA fine-tune on industrial DE+EN queries |
| LLM (sovereign default) | **Qwen3 4B Instruct** via Ollama | Strong DE+EN at ~2.5GB VRAM; truly on-prem |
| LLM (escalation) | Claude Sonnet 4.6 / GPT-4o | Opt-in via `sovereignty_mode=hybrid`, logged per Art. 13 |
| Agent framework | LangGraph | Observable trajectories, listwise state, streamable |
| Observability | Self-hosted Langfuse | Full trace, runs in Docker Compose alongside everything else |
| Deploy | Docker Compose + Vercel (frontend) | One command stands up the whole stack |

---

## EU AI Act compliance — designed in, not bolted on

| Requirement | Implementation |
|-------------|----------------|
| **Art. 6** — risk classification | System self-classifies as "limited risk" with documented reasoning. Seeded into `risk_classifications` table on first DB init. Visible at `/compliance`. |
| **Art. 13** — transparency to users | Every answer shows: source citations, LLM provider used, confidence score, local-vs-API routing decision. Persisted to `audit_events` table per agent node. |
| **Art. 14** — human oversight | All agent actions logged + reviewable from compliance dashboard with per-row provider/model/tokens/cost/latency. |
| **Art. 10** — data governance | Documented data sources, lineage from chunk back to source PDF + page number. |
| **GDPR Art. 25** — privacy by design | Audit log lives next to user data in same Postgres; configurable data residency via single DATABASE_URL. |
| **GDPR Art. 17** — right to erasure | `DELETE /query/{id}` and `DELETE /session/{id}` endpoints. UI exposes per-item delete + "erase data" session wipe. |
| **GDPR Art. 20** — portability | Audit log exposed as JSON via `GET /compliance/audit-log` (CSV export planned). |

---

## Eval results

**Setup:** 26 industrial PDFs across 8 Mittelstand brands. 909 pages indexed via ColPali v1.3 multi-vector visual embeddings. 714 synthetic DE+EN technical query-passage pairs generated via Claude Sonnet 4.6, stratified across brands, hard negatives mined via ColPali ANN. BGE-reranker-v2-m3 fine-tuned with LoRA (rank 16, ~2.6M trainable params, 0.46% of 570M base) for 3 epochs on 606 train / 108 held-out eval queries.

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

### End-to-end quality (RAGAS, hybrid mode, 30 held-out queries)

LLM-judged metrics over the full agent pipeline (ColPali retrieval → BGE LoRA rerank →
LangGraph multi-agent → Claude Sonnet 4.6 synthesizer). Judge LLM = Claude Sonnet 4.6.

| Metric | Score | What it measures |
|--------|------:|------------------|
| **faithfulness** | **0.752** | Fraction of answer claims that are grounded in the retrieved context (no hallucinations) |
| **context_precision** | **0.462** | Signal density of the retrieved top-K — how many top results were actually relevant |

`answer_relevancy` requires an embeddings model — the script now uses local BGE
multilingual embeddings by default so it works without an OpenAI key. The
2026-05-29 run was missing this metric.

Full results: [`data/eval/retrieval_results.json`](data/eval/retrieval_results.json),
[`data/eval/ragas_results.json`](data/eval/ragas_results.json).
Training history produced by [`ml/training/train_reranker.py`](ml/training/train_reranker.py).

---

## Run locally

**Prerequisites:**
- Docker Desktop with WSL2
- Node.js 20+
- Python 3.11+ (via [uv](https://docs.astral.sh/uv/))
- ~12 GB free disk (models + Postgres + container images)
- NVIDIA GPU with 6 GB+ VRAM recommended; CPU fallback available but slow

```bash
# 1. Spin up infra
git clone https://github.com/Ekansh1605/Lastenheft.git
cd Lastenheft
cp .env.example .env                          # add ANTHROPIC_API_KEY if you want hybrid mode
docker compose -f docker/docker-compose.yml --env-file .env up -d \
  postgres langfuse-db langfuse

# 2. Python deps + models
uv sync                                       # ~5 GB of ML deps (torch+cu124, ColPali, etc.)
uv run python scripts/prefetch_models.py      # downloads ColPali ~5 GB + ColQwen2 fallback
ollama pull qwen3:4b                          # sovereign default LLM (~2.5 GB)

# 3. Corpus (15 PDFs auto-downloaded from Siemens / Bosch / Festo / TRUMPF / KUKA / SICK / SEW)
uv run python scripts/download_sample_pdfs.py
uv run python -m ml.ingest.cli ingest-dir data/pdfs

# 4. (Optional) reproduce the eval numbers above
uv run python -m ml.training.gen_synth_queries --sample 250 --hard-negs 5     # ~$4 API
uv run python -m ml.training.train_reranker --epochs 3 --batch 4 --lr 2e-4   # ~2 hr RTX 3060
uv run python -m ml.training.eval_retrieval --eval-split 0.15

# 5. Run the API + UI
uv run uvicorn api.main:app                    # backend on :8000
cd web && npm install && npm run dev           # frontend on :3000
```

Open http://localhost:3000.

### Configuration knobs (env vars)

| Var | Default | Effect |
|---|---|---|
| `ALLOW_API_LLM` | `true` | Set `false` in public deploys to force every request to local Qwen3 regardless of UI mode. Prevents API-cost drain if URL is scraped. |
| `RATE_LIMIT_PER_MINUTE` | `10` | Per-IP throttle on `/query` and `/query/stream`. |
| `AGENT_TIMEOUT_SECONDS` | `180` | Hard kill for hung agent runs. Returns 504. |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated allowlist. |
| `OLLAMA_HOST` | `http://localhost:11434` | Local LLM endpoint. |
| `OLLAMA_MODEL` | `qwen3:4b` | Local generation model. |
| `DATABASE_URL` | `postgresql://lastenheft:lastenheft@localhost:5433/lastenheft` | Note port 5433 (5432 collides with system Postgres on many dev machines). |

---

## Production hardening checklist

What I shipped that takes this past "portfolio demo" into something I'd put behind a paying customer:

- ✅ Per-IP rate limiting (slowapi) with 429 + clear error
- ✅ Hard agent timeout via `asyncio.wait_for` → 504 with actionable message
- ✅ SSE client-disconnect detection → cancels GPU work mid-flight, sends `:keepalive` between chunks
- ✅ LLM-provider fallback (API failure → local Qwen3, tagged in audit log)
- ✅ UUID validation on all path/query params
- ✅ `ALLOW_API_LLM` kill-switch for cost safety in public demos
- ✅ Configurable CORS origins via env var
- ✅ GDPR Article 17 right-to-erasure: per-query DELETE and full-session wipe
- ✅ Idempotent ingestion (sha256 dedup, `ON CONFLICT DO UPDATE` on every write)
- ✅ Audit log with provider / model / tokens / cost / latency per agent node
- ✅ Audit log pagination (limit + offset, total count for UI footer)
- ✅ Mobile-responsive UI (sidebar collapses to drawer < md)
- ✅ Try/except around audit writes — auditing never breaks the user response
- ✅ Schema migrations live in `docker/init-db/` (idempotent SQL)

What I deliberately deferred (would ship for v1.0):

- 🟡 Production auth (sessions are unsigned UUIDs — single-user demo only)
- 🟡 Tenant isolation enforcement at row level (schema supports tenant_id; not enforced)
- 🟡 Prompt-injection mitigation beyond input length cap
- 🟡 Audit log CSV/JSON export endpoint (currently visible in dashboard only)
- 🟡 Foreign key from `audit_events.query_id` → `queries.id` (currently joined by session_id)
- 🟡 Background workers for ingest (currently inline; fine for 26 PDFs, breaks at 10k)
- 🟡 Observability via Langfuse SDK (containers run, traces not yet emitted from agent nodes)

---

## Curated demo corpus

26 publicly-available industrial documents from 8 major German Mittelstand brands. Mix of German + English. ~85 MB total.

| Brand | Domain | Docs |
|-------|--------|------|
| Siemens SIMATIC | Industrial automation / PLC | 7 (3 EN + 4 DE) |
| Festo | Pneumatics (ISO 15552 cylinders) | 5 (3 EN + 2 DE) |
| SICK | Industrial sensors | 4 (EN) |
| TRUMPF | Laser / CNC machine tools | 3 (EN) |
| Bosch Rexroth | Drives + hydraulic valves | 3 (EN) |
| KUKA | Industrial robotics | 1 (EN, 27 MB / ~100+ pages) |
| SEW Eurodrive | Drives / Movigear | 1 (DE) |
| EU regulatory | AI Act + Machinery Regulation | 2 (EN) |

URLs in [`scripts/download_sample_pdfs.py`](scripts/download_sample_pdfs.py). All sourced from publishers' public download portals — verified live May 2026.

---

## License

MIT — built as a portfolio piece by **[Ekansh Sharma](https://github.com/Ekansh1605)** ([linkedin.com/in/ekansh-sharma16](https://linkedin.com/in/ekansh-sharma16)).

Targeting AI Engineer / ML Engineer / Data Scientist / Full-stack roles in the German industrial Mittelstand.
