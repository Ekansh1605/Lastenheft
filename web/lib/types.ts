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

export interface RiskClassification {
  component: string;
  category: "minimal" | "limited" | "high" | "unacceptable";
  article_refs: string[];
  rationale: string;
  mitigations: string[];
}

export type StreamUpdate =
  | { type: "node"; node: string; trace: TraceEvent[]; partial_answer?: string; citations?: Citation[] }
  | { type: "done"; final: QueryResponse };
