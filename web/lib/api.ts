// Thin client for the Lastenheft FastAPI backend.

import type {
  AuditEvent, Citation, HistoryItem, QueryResponse, ReplayedQuery,
  RiskClassification, SovereigntyMode, TraceEvent,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export interface StreamHandlers {
  onNode?: (node: string, trace: TraceEvent[], citations?: Citation[]) => void;
  onDone?: (final: QueryResponse) => void;
  onError?: (err: Error) => void;
}

export function streamQuery(
  query: string,
  sovereigntyMode: SovereigntyMode,
  sessionId: string,
  handlers: StreamHandlers,
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const r = await fetch(`${API_BASE}/query/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          sovereignty_mode: sovereigntyMode,
          session_id: sessionId,
        }),
        signal: controller.signal,
      });
      if (!r.body) throw new Error("no response body");

      const reader = r.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let currentEvent = "message";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";
        for (const raw of parts) {
          let dataLine = "";
          for (const line of raw.split("\n")) {
            if (line.startsWith("event:")) currentEvent = line.slice(6).trim();
            else if (line.startsWith("data:")) dataLine += line.slice(5).trim();
          }
          if (!dataLine) continue;
          try {
            const parsed = JSON.parse(dataLine);
            if (currentEvent === "done") {
              handlers.onDone?.(parsed);
            } else if (parsed.type === "node") {
              handlers.onNode?.(parsed.node, parsed.trace ?? [], parsed.citations);
            }
          } catch {
            // ignore non-JSON keepalive payloads
          }
          currentEvent = "message";
        }
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") handlers.onError?.(e as Error);
    }
  })();

  return () => controller.abort();
}

export async function fetchHistory(sessionId: string): Promise<HistoryItem[]> {
  const r = await fetch(`${API_BASE}/query/history?session_id=${encodeURIComponent(sessionId)}`);
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json();
}

export async function fetchQuery(queryId: string): Promise<ReplayedQuery> {
  const r = await fetch(`${API_BASE}/query/${encodeURIComponent(queryId)}`);
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json();
}

export async function fetchRiskClassifications(): Promise<RiskClassification[]> {
  const r = await fetch(`${API_BASE}/compliance/risk-classifications`);
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json();
}

export async function fetchAuditLog(limit = 100): Promise<{ events: AuditEvent[]; total: number }> {
  const r = await fetch(`${API_BASE}/compliance/audit-log?limit=${limit}`);
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json();
}
