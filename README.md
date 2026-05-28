# WerkDocs

> Sovereign multimodal document intelligence for industrial manufacturing — EU AI Act-compliant by design.

Self-hosted RAG over technical PDFs (engineering drawings, datasheets, BoMs, SOPs) in German + English, without sending IP to OpenAI. Built for Mittelstand manufacturers who can't compromise on Geschäftsgeheimnis or compliance.

**Status:** 🚧 Building — Day 1 of 5 (started 2026-05-28)

---

## Why this exists

German industrial Mittelstand has 40+ years of technical documentation locked in PDFs — engineering drawings, datasheets, maintenance manuals, certifications, BoMs — often mixed German + English, full of tables and diagrams that OCR mangles. They need AI to unlock this knowledge, but:

1. **They cannot send sensitive IP to OpenAI** — Geschäftsgeheimnis / sovereignty is non-negotiable
2. **EU AI Act enforcement is active in 2026** — industrial AI often classifies as high-risk under Article 6; every deployment needs documented risk classification, transparency, audit trails
3. **They need engineering precision** — vibes-based LLM output fails when tolerances matter
4. **Existing solutions (Microsoft Copilot, ChatGPT Enterprise) violate sovereignty requirements**

WerkDocs is designed from the ground up for these constraints.

---

## Architecture

```
Next.js 15 frontend  ──►  FastAPI orchestration  ──►  LangGraph multi-agent
                                    │                  (planner / retriever /
                                    │                   validator / synthesizer)
                                    ▼
                          ┌─────────┴─────────┐
                          ▼                   ▼
              Multimodal Retrieval     LLM Router
              (ColQwen2, no OCR)       (local Qwen3 4B ↔ API)
                          │                   │
                          ▼                   │
              Postgres + pgvector             │
                          │                   │
                          ▼                   ▼
              Audit log + AI Act compliance dashboard
```

**Key choices:**

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Frontend | Next.js 15 + Tailwind + shadcn | Modern, type-safe, fast |
| Auth + DB | Supabase + Postgres + pgvector | RLS for multi-tenant, mature pgvector |
| ML inference | FastAPI (Python 3.11) | Industry-standard ML serving |
| Visual retrieval | **ColQwen2** (ColPali fallback) | No OCR — handles diagrams, tables, drawings directly |
| Reranker | BGE-reranker-v2-m3, LoRA fine-tuned on DE+EN technical queries | Real ML signal, big quality lift |
| LLM (local) | **Qwen3 4B Instruct** via Ollama | Sovereign default, strong DE+EN |
| LLM (API) | Claude Sonnet 4.6 / GPT-4o | Opt-in for complex reasoning, logged per AI Act Art. 13 |
| Agents | LangGraph | Observable trajectories, production-grade |
| Observability | Self-hosted Langfuse | Full traces, no data leaves your infra |
| Deploy | Docker Compose | One command: `docker compose up` |

---

## EU AI Act compliance design

This system is designed against EU AI Act articles, not retrofitted. README mapping:

| Requirement | Implementation |
|-------------|----------------|
| Art. 6 — risk classification | System self-classifies as "limited risk" with documented reasoning (RAG over docs ≠ safety-critical decision-making) |
| Art. 13 — transparency to users | Every answer shows: source citations, LLM provider used, confidence score, local-vs-API routing decision |
| Art. 14 — human oversight | All agent actions logged + reviewable; "Why this answer?" explanation modal |
| Art. 10 — data governance | Documented data sources, lineage from chunk back to source PDF + page + bbox |
| GDPR Art. 25 — privacy by design | Optional PII detector at ingest; full audit log; configurable data residency |
| GDPR Art. 17 — right to erasure | DELETE cascades from documents → embeddings → audit logs (with retention exception) |

Compliance dashboard exposes all of the above to admin users.

---

## Eval results

_To be populated after Day 2 reranker training + Day 3 RAGAS run._

| Metric | Off-the-shelf | LoRA fine-tuned | Δ |
|--------|---------------|-----------------|---|
| Retrieval nDCG@10 | TBD | TBD | TBD |
| Retrieval MRR | TBD | TBD | TBD |
| RAGAS faithfulness | TBD | TBD | TBD |
| RAGAS answer relevancy | TBD | TBD | TBD |
| RAGAS context precision | TBD | TBD | TBD |
| Latency p50 (local LLM) | TBD | TBD | TBD |
| Latency p50 (API LLM) | TBD | TBD | TBD |
| Cost per query (API) | TBD | TBD | TBD |

---

## Run locally

**Prerequisites:**
- Docker Desktop with WSL2
- Node.js 20+
- Python 3.11+
- ~10GB free disk (models + Postgres data)
- NVIDIA GPU with 6GB+ VRAM recommended (CPU fallback available, slower)

**One-command boot:**

```bash
git clone https://github.com/Ekansh1605/werkdocs.git
cd werkdocs
cp .env.example .env  # add your API keys
docker compose up -d
pnpm install && pnpm dev
```

Open http://localhost:3000.

---

## Limitations & future work

- **VRAM:** 6GB GPU shares VRAM between ColQwen2 (~5GB FP16 / ~2.5GB Q4) and Qwen3 4B Q4 (~2.5GB). Tight but works.
- **Reranker training data:** Synthetic queries from GPT-4o. Real customer query logs would improve recall on niche technical jargon.
- **PII detector:** Currently rule-based (Microsoft Presidio). A fine-tuned NER for German industrial PII would be next.
- **No SAP integration yet.** Most Mittelstand have SAP/MES systems — connector would be production deployment work.
- **Single-tenant in current MVP.** RLS schema is multi-tenant-ready; UI/billing is not.

---

## License

MIT — built as a portfolio piece by [Ekansh Sharma](https://github.com/Ekansh1605).
