// Mirrors the Pydantic models in api/routers/query.py + api/routers/compliance.py
// Keep in sync if backend shapes change.

export type SovereigntyMode = "local-only" | "hybrid" | "api-only";

export interface Citation {
  page_id: string;
  document_id: string;
  filename: string;
  page_number: number;
  score: number;
  snippet: string;
}

export interface TraceEvent {
  step: string;
  detail: string;
  latency_ms: number;
  payload: Record<string, unknown>;
}

export interface QueryResponse {
  query_id: string;
  user_query: string;
  answer: string;
  citations: Citation[];
  llm_provider: string;
  llm_model: string;
  confidence: number;
  sovereignty_mode: SovereigntyMode;
  needs_escalation: boolean;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  total_latency_ms: number;
  session_id: string;
  trace: TraceEvent[];
}

export interface HistoryItem {
  id: string;
  user_query: string;
  llm_provider: string;
  llm_model: string;
  sovereignty_mode: SovereigntyMode;
  cost_usd: number;
  latency_ms: number;
  created_at: string;
}

export interface ReplayedQuery {
  query_id: string;
  session_id: string;
  user_query: string;
  planner: { sub_queries?: string[]; complexity?: number; rationale?: string } | null;
  retrieved_pages: { page_id?: string; filename?: string; page_number?: number; score?: number }[];
  answer: string;
  llm_provider: string;
  llm_model: string;
  sovereignty_mode: SovereigntyMode;
  confidence: number;
  latency_ms: number;
  cost_usd: number;
  created_at: string;
}

export interface RiskClassification {
  component: string;
  category: "minimal" | "limited" | "high" | "unacceptable";
  article_refs: string[];
  rationale: string;
  mitigations: string[];
}

export interface AuditEvent {
  id: string;
  session_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  llm_provider: string | null;
  llm_model: string | null;
  token_input: number | null;
  token_output: number | null;
  cost_usd: number | null;
  latency_ms: number | null;
  created_at: string;
}
