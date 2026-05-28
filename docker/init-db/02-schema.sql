-- =====================================================================
-- Lastenheft schema
-- Multimodal RAG over industrial PDFs with EU AI Act compliance audit
-- =====================================================================

-- ---------- core: documents & pages ----------

CREATE TABLE IF NOT EXISTS documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000',
    filename        TEXT NOT NULL,
    sha256          TEXT NOT NULL UNIQUE,
    page_count      INTEGER NOT NULL,
    language        TEXT,                                 -- detected dominant language (de/en/mixed)
    source          TEXT,                                 -- e.g. "siemens-catalog", "user-upload"
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    pii_scan_status TEXT NOT NULL DEFAULT 'skipped',      -- skipped|clean|flagged
    pii_findings    JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    indexed_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_documents_tenant ON documents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(created_at DESC);

CREATE TABLE IF NOT EXISTS pages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number     INTEGER NOT NULL,
    width           INTEGER,
    height          INTEGER,
    image_path      TEXT NOT NULL,                        -- rasterized page on disk / object store
    extracted_text  TEXT,                                 -- bonus: text fallback if extractable
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, page_number)
);

CREATE INDEX IF NOT EXISTS idx_pages_document ON pages(document_id);

-- ---------- embeddings: ColQwen2 multi-vector ----------
-- ColQwen2 / ColPali produce MULTI-vector embeddings per page (many patches × 128 dims).
-- For pgvector, we store the mean-pooled single-vector for cheap ANN, plus all patch vectors
-- for late-interaction reranking.

CREATE TABLE IF NOT EXISTS page_embeddings (
    page_id           UUID PRIMARY KEY REFERENCES pages(id) ON DELETE CASCADE,
    model             TEXT NOT NULL,                      -- e.g. "colqwen2-v1.0"
    mean_vector       vector(128) NOT NULL,               -- mean-pool of all patches for ANN
    patch_vectors     BYTEA NOT NULL,                     -- packed float16: [n_patches, 128]
    n_patches         INTEGER NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- HNSW index for fast cosine ANN over mean vectors
CREATE INDEX IF NOT EXISTS idx_page_embeddings_hnsw
    ON page_embeddings USING hnsw (mean_vector vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ---------- AI Act audit log ----------
-- Every query, retrieval, LLM call, and routing decision logged per Art. 13/14.

CREATE TABLE IF NOT EXISTS audit_events (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000',
    user_id           TEXT,
    session_id        UUID,
    event_type        TEXT NOT NULL,                      -- query|retrieval|llm_call|routing_decision|document_upload|document_delete|pii_detection|explanation_request
    payload           JSONB NOT NULL,                     -- structured event data
    llm_provider      TEXT,                               -- anthropic|openai|ollama-local|null
    llm_model         TEXT,
    token_input       INTEGER,
    token_output      INTEGER,
    cost_usd          NUMERIC(10, 6),
    latency_ms        INTEGER,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_events_tenant_created ON audit_events(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_session ON audit_events(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_type ON audit_events(event_type);

-- ---------- Sessions + queries (for transparency reports) ----------

CREATE TABLE IF NOT EXISTS query_sessions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000',
    user_id           TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS queries (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id        UUID NOT NULL REFERENCES query_sessions(id) ON DELETE CASCADE,
    user_query        TEXT NOT NULL,
    planner_decomposition JSONB,
    retrieved_pages   JSONB NOT NULL DEFAULT '[]'::jsonb, -- [{page_id, score, citations}, ...]
    final_answer      TEXT,
    llm_provider      TEXT NOT NULL,
    llm_model         TEXT NOT NULL,
    sovereignty_mode  TEXT NOT NULL,                      -- local-only|hybrid|api-only
    confidence        NUMERIC(4, 3),                      -- 0..1 self-rated confidence
    latency_ms        INTEGER NOT NULL,
    cost_usd          NUMERIC(10, 6) NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_queries_session ON queries(session_id);
CREATE INDEX IF NOT EXISTS idx_queries_created ON queries(created_at DESC);

-- ---------- Risk classifications (Art. 6) ----------
-- The system self-classifies itself per AI Act risk category.

CREATE TABLE IF NOT EXISTS risk_classifications (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component         TEXT NOT NULL,                      -- "retrieval"|"generation"|"system-overall"
    category          TEXT NOT NULL,                      -- minimal|limited|high|unacceptable
    article_refs      TEXT[] NOT NULL,                    -- ['Article 6', 'Annex III']
    rationale         TEXT NOT NULL,
    mitigations       JSONB NOT NULL DEFAULT '[]'::jsonb,
    classified_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    classified_by     TEXT NOT NULL                       -- 'system-default' or admin user id
);

-- Seed: classify this system itself
INSERT INTO risk_classifications (component, category, article_refs, rationale, mitigations, classified_by)
VALUES
    ('system-overall', 'limited', ARRAY['Article 6', 'Article 13', 'Article 50'],
     'Document Q&A over industrial technical documentation. Not a safety component of machinery (Annex I). Not making consequential automated decisions about persons (Annex III). Transparency obligation applies under Art. 50 since LLM-generated content is exposed to humans.',
     '["Citation overlay on every answer", "Provider disclosure per answer", "Audit log per Art. 13", "Human-in-the-loop validation step"]'::jsonb,
     'system-default'),
    ('retrieval', 'minimal', ARRAY['Article 6'],
     'Pure information retrieval with no automated decision-making. Outputs ranked passages for human review.',
     '["Relevance scores exposed to user"]'::jsonb,
     'system-default'),
    ('generation', 'limited', ARRAY['Article 13', 'Article 50'],
     'LLM-generated summaries of retrieved passages. Users must be informed they are interacting with AI-generated content.',
     '["AI provider visible per response", "Confidence score exposed", "Always cites source passages", "User can request raw source view"]'::jsonb,
     'system-default')
ON CONFLICT DO NOTHING;
