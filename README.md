# Lastenheft

> Sovereign multimodal RAG for the German industrial Mittelstand.
> Because Geschäftsgeheimnis doesn't belong in OpenAI's logs.

**Lastenheft** is a production-grade Q&A system over technical PDFs from German industrial manufacturers (Siemens, Bosch Rexroth, TRUMPF, KUKA, Festo, SICK, SEW Eurodrive). It handles engineering drawings, datasheets, BoMs, and maintenance manuals in German + English without OCR, without sending IP to OpenAI, and with EU AI Act compliance designed in from the schema layer up.

Named after the *Lastenheft*: the customer requirements specification document every German engineer at Bosch / Siemens / Trumpf / ZF starts a project with.

---

## Why this exists

German industrial Mittelstand has 40+ years of technical documentation locked in PDFs. They need AI to unlock it, but:

1. **They cannot send sensitive IP to OpenAI.** Geschäftsgeheimnis is non-negotiable.
2. **EU AI Act enforcement is active in 2026.** Industrial AI often classifies as high-risk under Article 6; every deployment needs documented risk classification, transparency, audit trails.
3. **They need engineering precision.** Vibes-based LLM output fails when tolerances and certifications matter.
4. **Existing solutions (Microsoft Copilot for M365, ChatGPT Enterprise) violate sovereignty requirements.**

Lastenheft solves all four.

---

## What it does

A user asks an industrial question in German or English. The multi-agent system decomposes it. ColPali multimodal retrieval finds the relevant pages without OCR (it works directly on diagrams, tables, technical drawings). A LoRA-fine-tuned BGE reranker picks the top 5. A local Qwen3 4B model (or an opt-in API LLM) writes the answer with bracketed citations. Every step writes an audit row for EU AI Act Article 13 transparency.

The user sees the live agent trajectory, a cited answer, the citation cards, and can replay any past query from the sidebar history.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│ Next.js 16 frontend                                                  │
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
| Visual retrieval | **ColPali v1.3** (PaliGemma-based) | No OCR. Embeds page IMAGES directly. Handles diagrams, tables, drawings that text retrievers miss. |
| Reranker | BGE-reranker-v2-m3 (568M) + LoRA (~2.6M trainable) | Cross-encoder for high-precision top-K. LoRA fine-tune on industrial DE+EN queries |
| LLM (sovereign default) | **Qwen3 4B Instruct** via Ollama | Strong DE+EN at ~2.5GB VRAM. Truly on-prem |
| LLM (escalation) | Claude Sonnet 4.6 / GPT-4o | Opt-in via `sovereignty_mode=hybrid`, logged per Art. 13 |
| Agent framework | LangGraph | Observable trajectories, listwise state, streamable |
| Observability | Self-hosted Langfuse | Full trace, runs in Docker Compose alongside everything else |
| Deploy | Docker Compose + Vercel (frontend) | One command stands up the whole stack |

---

## EU AI Act compliance: designed in, not bolted on

| Requirement | Implementation |
|-------------|----------------|
| **Art. 6**, risk classification | System self-classifies as "limited risk" with documented reasoning. Seeded into `risk_classifications` table on first DB init. Visible at `/compliance`. |
| **Art. 13**, transparency to users | Every answer shows: source citations, LLM provider used, confidence score, local-vs-API routing decision. Persisted to `audit_events` table per agent node. |
| **Art. 14**, human oversight | All agent actions logged + reviewable from compliance dashboard with per-row provider/model/tokens/cost/latency. |
| **Art. 10**, data governance | Documented data sources, lineage from chunk back to source PDF + page number. |
| **GDPR Art. 25**, privacy by design | Audit log lives next to user data in same Postgres. Configurable data residency via single DATABASE_URL. |
| **GDPR Art. 17**, right to erasure | `DELETE /query/{id}` and `DELETE /session/{id}` endpoints. UI exposes per-item delete + "erase data" session wipe. |
| **GDPR Art. 20**, portability | Audit log exposed as JSON via `GET /compliance/audit-log` (CSV export planned). |

---

## Eval results

**Setup:** 26 industrial PDFs across 8 Mittelstand brands. 909 pages indexed via ColPali v1.3 multi-vector visual embeddings. 714 synthetic DE+EN technical query-passage pairs generated via Claude Sonnet 4.6, stratified across brands, hard negatives mined via ColPali ANN. BGE-reranker-v2-m3 fine-tuned with LoRA (rank 16, ~2.6M trainable params, 0.46% of 570M base) for 3 epochs on 606 train / 108 held-out eval queries.

### Retrieval (full-corpus eval, 108 held-out queries, 909 candidate pages)

| Strategy | MRR | Hit@1 | Hit@5 | Hit@10 | nDCG@10 | median rank |
|----------|-----:|------:|------:|-------:|--------:|------------:|
| ColPali ANN only (baseline) | 0.341 | 20.4% | 45.4% | 61.1% | 0.395 | 3 |
| + BGE reranker (off-the-shelf) | 0.707 | 62.0% | 83.3% | 85.2% | 0.743 | 1 |
| + **BGE reranker (LoRA fine-tuned)** | **0.758** | **70.4%** | 82.4% | **85.2%** | **0.781** | **1** |

**LoRA fine-tune delta over off-the-shelf reranker: +5.1 pts MRR, +8.4 pts Hit@1, +3.8 pts nDCG@10.** The fine-tune learned to push the correct page to position 1 more confidently, which is exactly the property a citation-overlay UI cares about.

### In-training listwise accuracy (positive vs 4 hard negatives)

| Stage | Accuracy |
|-------|---------:|
| BGE-reranker-v2-m3 baseline | 0.843 |
| After epoch 1 | 0.889 |
| After epoch 2 | 0.861 |
| **After epoch 3 (saved)** | **0.898** |

### End-to-end quality (RAGAS, hybrid mode, 30 held-out queries)

LLM-judged metrics over the full agent pipeline (ColPali retrieval, BGE LoRA rerank, LangGraph multi-agent, Claude Sonnet 4.6 synthesizer). Judge LLM = Claude Sonnet 4.6.

| Metric | Score | What it measures |
|--------|------:|------------------|
| **faithfulness** | **0.752** | Fraction of answer claims grounded in retrieved context (no hallucinations) |
| **context_precision** | **0.462** | Signal density of the retrieved top-K |

`answer_relevancy` requires an embeddings model. The script now uses local BGE multilingual embeddings by default so it works without an OpenAI key.

Full results: [`data/eval/retrieval_results.json`](data/eval/retrieval_results.json), [`data/eval/ragas_results.json`](data/eval/ragas_results.json).

---

## Customizing for your hardware

The default config targets a 6 GB laptop GPU (RTX 3060 Mobile). If you have more VRAM, here is exactly what to change and what to expect.

### Swapping the visual embedder

The visual embedder is selected by an env var. The default is ColPali v1.3, which loads cleanly under transformers 4.x. Two strong alternatives:

```bash
# .env

# Default (3B, ~5.9 GB VRAM bf16) — best stability today
COLPALI_MODEL=vidore/colpali-v1.3

# ColQwen2 v1.0 (3B, similar VRAM) — slightly better on ViDoRe leaderboard
# but currently has a LoRA-adapter loading issue with newer colpali-engine
# releases. Try it; the loader in ml/ingest/embedder.py falls back gracefully.
COLPALI_MODEL=vidore/colqwen2-v1.0

# ColQwen2.5 v0.1 (3B) — newest in the family, late-2025 release
COLPALI_MODEL=vidore/colqwen2.5-v0.1
```

If you have a workstation GPU (24 GB+):

```bash
# ColPali-v1.3 with the larger PaliGemma-3b backbone runs comfortably
# alongside the BGE reranker. No code changes needed; just leave the
# COLPALI_MODEL on the default and increase the batch size:
INGEST_BATCH_SIZE=4
```

After swapping, you need to **re-ingest** the corpus because embeddings are model-specific:

```bash
# Wipe old embeddings (keeps documents + pages, just drops embeddings)
docker exec lastenheft-postgres psql -U lastenheft -d lastenheft \
  -c "TRUNCATE page_embeddings, pages, documents RESTART IDENTITY CASCADE;"
# Re-ingest
uv run python -m ml.ingest.cli ingest-dir data/pdfs
```

### Upgrading the local LLM (Qwen3 → larger)

`agents/llm_router.py` picks `qwen3:4b` by default. Bigger models give better answers but need more VRAM. Pull the one that fits, then update one env var:

| Model | VRAM (Q4) | DE+EN quality | Recommended if |
|-------|----------:|---------------|----------------|
| `qwen3:4b` (default) | ~2.5 GB | Good | 6 GB laptop |
| `qwen3:8b` | ~4.5 GB | Better | 8-12 GB GPU |
| `qwen3:14b` | ~9 GB | Strong | 12-16 GB GPU |
| `qwen3:32b` | ~20 GB | Near-API | 24 GB+ workstation |
| `llama3.3:70b` | ~40 GB | API-tier | 2x 24 GB or A100 |
| `deepseek-r1:32b` | ~20 GB | Reasoning-heavy | When you want chain-of-thought |
| `mistral-small3.2:24b` | ~14 GB | Strong on EN | 16+ GB GPU |

```bash
# Pull the model via Ollama
ollama pull qwen3:14b

# Tell Lastenheft to use it
# .env
OLLAMA_MODEL=qwen3:14b
```

If you're on **CPU only** (no GPU):

```bash
# Smallest viable model with usable quality
ollama pull qwen3:1.7b
OLLAMA_MODEL=qwen3:1.7b
# Generation will be 5-15 tokens/sec; the agent will still work but
# expect 30-60s per answer.
```

### Better reranker (more data, more epochs, bigger LoRA)

The default LoRA fine-tune uses 250 stratified pages × 3 synth queries = 750 training pairs, 3 epochs, rank 16. To squeeze more performance:

```bash
# 1. Generate more synthetic queries (cost scales linearly: $4 for 250 pages,
#    $16 for 1000). Stratification still works at any sample count.
uv run python -m ml.training.gen_synth_queries \
    --sample 1000 \
    --hard-negs 8 \
    --out data/eval/synth_queries_v2.jsonl

# 2. Train longer with larger LoRA rank. Rank 32 doubles trainable params
#    but stays under 1% of base. Batch 8 needs ~6 GB VRAM.
uv run python -m ml.training.train_reranker \
    --synth data/eval/synth_queries_v2.jsonl \
    --epochs 5 \
    --batch 8 \
    --lr 1e-4 \
    --lora-r 32 \
    --lora-alpha 64 \
    --max-negs 6 \
    --eval-split 0.1 \
    --out models/reranker-lora-v2
```

Diminishing returns kick in around epoch 4 for most ranker setups; we add early stopping in a comment in `train_reranker.py` if you want to wire it up.

### Swapping the reranker base entirely

The cross-encoder is loaded by env var, so trying a different family is a one-line change:

```bash
# .env

# Default. 568M params. XLM-RoBERTa large base. Strong DE+EN.
RERANKER_BASE=BAAI/bge-reranker-v2-m3

# Smaller (278M), faster, English-leaning. Good for English-only corpora.
RERANKER_BASE=BAAI/bge-reranker-base

# Jina v2 (multilingual). 278M. Trained on more recent web data.
RERANKER_BASE=jinaai/jina-reranker-v2-base-multilingual

# Larger BGE if you have 12+ GB VRAM. ~1.1B params.
RERANKER_BASE=BAAI/bge-reranker-v2-gemma
```

After swap, retrain the LoRA. The script handles any sequence-classification cross-encoder transparently as long as it's a HuggingFace model with `num_labels=1`.

### Improving synthetic data quality

`ml/training/gen_synth_queries.py` uses a fixed prompt that asks Claude to produce a short-factual, an analytical, and an opposite-language question per page. Two ways to make the data better:

**1) Larger judge model for the generation step**

The default is `claude-sonnet-4-6`. If you want sharper questions:

```python
# In ml/training/gen_synth_queries.py, function call_anthropic, change:
def call_anthropic(prompt: str, model: str = "claude-opus-4-7") -> str:
```

Cost: ~5x but the questions are noticeably more domain-specific.

**2) Domain-targeted prompt rewrites**

The current `PROMPT_TEMPLATE` is generic for "industrial documentation". If you're targeting one vertical (e.g., automotive harness specs, pharma SOPs, plumbing certifications), edit the few-shot examples in the template. The reranker is sensitive to query distribution, so domain-matched synth examples lift end-to-end metrics more than just adding raw volume.

### Multimodal vs text retrieval: when to switch

ColPali shines on pages with visual structure (tables, diagrams, schematics). On pure-text pages it sometimes loses to a strong text embedder. If your corpus is mostly text (legal documents, policy PDFs), consider a hybrid:

```python
# Sketch — not wired by default. See agents/nodes.py:retriever.
# Run BOTH ColPali ANN AND a text embedder (e.g., BGE-multilingual on
# extracted_text) and take the union of their top-K candidates before
# the reranker. Best of both worlds.
from langchain_huggingface import HuggingFaceEmbeddings
text_embed = HuggingFaceEmbeddings(model_name="BAAI/bge-multilingual-gemma2")
```

In our benchmarks, the multimodal-only setup was the clear winner on the Siemens/Bosch/TRUMPF corpus because those documents are 60% tables and schematics. On legal corpora the hybrid approach typically adds +2-5 pts Hit@10.

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

# 3. Corpus (26 PDFs auto-downloaded from Siemens / Bosch / Festo / TRUMPF / KUKA / SICK / SEW)
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
| `COLPALI_MODEL` | `vidore/colpali-v1.3` | Visual embedder. See "Customizing for your hardware". |
| `RERANKER_BASE` | `BAAI/bge-reranker-v2-m3` | Cross-encoder reranker base. |
| `RERANKER_LORA` | `models/reranker-lora` | Path to LoRA adapter (skipped if absent). |
| `DATABASE_URL` | `postgresql://lastenheft:lastenheft@localhost:5433/lastenheft` | Note port 5433 (5432 collides with system Postgres on many dev machines). |

---

## Production hardening checklist

What shipped that takes this past "portfolio demo" into something I'd put behind a paying customer:

- Per-IP rate limiting (slowapi) with 429 + clear error
- Hard agent timeout via `asyncio.wait_for`, returns 504 with actionable message
- SSE client-disconnect detection cancels GPU work mid-flight, sends `:keepalive` between chunks
- LLM-provider fallback (API failure → local Qwen3, tagged in audit log)
- UUID validation on all path/query params
- `ALLOW_API_LLM` kill-switch for cost safety in public demos
- Configurable CORS origins via env var
- GDPR Article 17 right-to-erasure: per-query DELETE and full-session wipe
- Idempotent ingestion (sha256 dedup, `ON CONFLICT DO UPDATE` on every write)
- Audit log with provider / model / tokens / cost / latency per agent node
- Audit log pagination (limit + offset, total count for UI footer)
- Mobile-responsive UI (sidebar collapses to drawer below md breakpoint)
- Try/except around audit writes so auditing never breaks the user response
- Schema migrations in `docker/init-db/` (idempotent SQL)
- Foreign key from `audit_events.query_id` to `queries.id` with ON DELETE CASCADE

What I deliberately deferred (would ship for v1.0):

- Production auth (sessions are unsigned UUIDs, single-user demo only)
- Tenant isolation enforcement at row level (schema supports tenant_id; not enforced)
- Prompt-injection mitigation beyond input length cap
- Audit log CSV/JSON export endpoint (currently visible in dashboard only)
- Background workers for ingest (currently inline; fine for 26 PDFs, breaks at 10k)
- Langfuse SDK is wired but you need to populate `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` after your first login at http://localhost:3001

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

URLs in [`scripts/download_sample_pdfs.py`](scripts/download_sample_pdfs.py). All sourced from publishers' public download portals, verified live May 2026.

To use your own corpus, drop PDFs into `data/pdfs/` and run `uv run python -m ml.ingest.cli ingest-dir data/pdfs`. The pipeline is idempotent on SHA256, so re-running over an existing folder only processes new files.

---

## License

MIT. Built by **[Ekansh Sharma](https://github.com/Ekansh1605)** ([linkedin.com/in/ekansh-sharma16](https://linkedin.com/in/ekansh-sharma16)).

Targeting AI Engineer / ML Engineer / Data Scientist / Full-stack roles in the German industrial Mittelstand.
