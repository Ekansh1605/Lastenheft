"use client";

import { useCallback, useEffect, useState } from "react";
import { AgentTrace } from "@/components/agent-trace";
import { AnswerDisplay } from "@/components/answer-display";
import { CitationCard } from "@/components/citation-card";
import { SidebarHistory } from "@/components/sidebar-history";
import { SovereigntyToggle } from "@/components/sovereignty-toggle";
import {
  deleteQuery, deleteSession, fetchHistory, fetchQuery, streamQuery,
} from "@/lib/api";
import { getSessionId, newSessionId } from "@/lib/session";
import type {
  Citation, HistoryItem, QueryResponse, ReplayedQuery,
  SovereigntyMode, TraceEvent,
} from "@/lib/types";
import { Send, Loader2, RotateCcw, Menu, ArrowRight, Trash } from "lucide-react";

const EXAMPLES = [
  {
    text: "What is the maximum sheet thickness for stainless steel on the TruLaser 2030 fiber?",
    brand: "TRUMPF",
    lang: "EN",
  },
  {
    text: "Welche Schutzart hat das DSBC Normzylinder?",
    brand: "Festo",
    lang: "DE",
  },
  {
    text: "What is the operating voltage range of the IndraDrive Cs?",
    brand: "Bosch Rexroth",
    lang: "EN",
  },
  {
    text: "Was sind die Anforderungen der EU-Maschinenverordnung 2023/1230?",
    brand: "EU AI Act",
    lang: "DE",
  },
];

function replayToResponse(r: ReplayedQuery): QueryResponse {
  return {
    query_id: r.query_id,
    user_query: r.user_query,
    answer: r.answer,
    citations: (r.retrieved_pages || []).map((p) => ({
      page_id: p.page_id ?? "",
      document_id: "",
      filename: p.filename ?? "",
      page_number: p.page_number ?? 0,
      score: p.score ?? 0,
      snippet: "",
    })),
    llm_provider: r.llm_provider,
    llm_model: r.llm_model,
    confidence: r.confidence,
    sovereignty_mode: r.sovereignty_mode,
    needs_escalation: false,
    input_tokens: 0,
    output_tokens: 0,
    cost_usd: r.cost_usd,
    total_latency_ms: r.latency_ms,
    session_id: r.session_id,
    trace: r.trace ?? [],
  };
}

export default function Home() {
  const [sessionId, setSessionId] = useState<string>("");
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [activeQueryId, setActiveQueryId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SovereigntyMode>("hybrid");
  const [trace, setTrace] = useState<TraceEvent[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [inFlight, setInFlight] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [abort, setAbort] = useState<(() => void) | null>(null);
  const [replayMode, setReplayMode] = useState(false);

  useEffect(() => { setSessionId(getSessionId()); }, []);

  const refreshHistory = useCallback(async (id: string) => {
    try { setHistory(await fetchHistory(id)); } catch { /* silent */ }
  }, []);

  useEffect(() => { if (sessionId) refreshHistory(sessionId); }, [sessionId, refreshHistory]);

  const onSubmit = useCallback(
    (e?: React.FormEvent) => {
      e?.preventDefault();
      if (!query.trim() || inFlight || !sessionId) return;
      setReplayMode(false);
      setActiveQueryId(null);
      setTrace([]);
      setCitations([]);
      setResult(null);
      setError(null);
      setInFlight("planner");

      const cancel = streamQuery(query.trim(), mode, sessionId, {
        onNode: (node, evs, cits) => {
          if (evs?.length) setTrace((prev) => [...prev, ...evs]);
          if (cits?.length) setCitations(cits);
          const order = ["planner", "retriever", "validator", "synthesizer"];
          const idx = order.indexOf(node);
          setInFlight(idx >= 0 && idx + 1 < order.length ? order[idx + 1] : null);
        },
        onDone: (final) => {
          setResult(final);
          setActiveQueryId(final.query_id);
          setInFlight(null);
          setAbort(null);
          refreshHistory(sessionId);
        },
        onError: (e) => {
          setError(e.message);
          setInFlight(null);
          setAbort(null);
        },
      });
      setAbort(() => cancel);
    },
    [query, mode, inFlight, sessionId, refreshHistory],
  );

  const onCancel = useCallback(() => {
    abort?.();
    setInFlight(null);
    setAbort(null);
  }, [abort]);

  const onNewQuery = useCallback(() => {
    onCancel();
    setQuery("");
    setTrace([]);
    setCitations([]);
    setResult(null);
    setError(null);
    setActiveQueryId(null);
    setReplayMode(false);
    setSidebarOpen(false);
  }, [onCancel]);

  const onNewSession = useCallback(async () => {
    if (!confirm("Start a brand-new session?\n\nYour current sidebar will be cleared (the data stays in the audit log).")) return;
    const id = newSessionId();
    setSessionId(id);
    setHistory([]);
    onNewQuery();
  }, [onNewQuery]);

  const onDeleteHistoryItem = useCallback(
    async (id: string) => {
      try {
        await deleteQuery(id);
        setHistory((prev) => prev.filter((h) => h.id !== id));
        if (activeQueryId === id) onNewQuery();
      } catch (e) {
        setError(`Delete failed: ${(e as Error).message}`);
      }
    },
    [activeQueryId, onNewQuery],
  );

  const onWipeSession = useCallback(async () => {
    if (!sessionId) return;
    if (!confirm("Delete ALL queries in this session from the server?\n\nThis is GDPR Article 17 right-to-erasure — irreversible.")) return;
    try {
      await deleteSession(sessionId);
      setHistory([]);
      onNewQuery();
    } catch (e) {
      setError(`Session wipe failed: ${(e as Error).message}`);
    }
  }, [sessionId, onNewQuery]);

  const onSelectHistory = useCallback(
    async (id: string) => {
      onCancel();
      setActiveQueryId(id);
      setReplayMode(true);
      setError(null);
      setSidebarOpen(false);
      try {
        const r = await fetchQuery(id);
        setQuery(r.user_query);
        setMode(r.sovereignty_mode);
        const synthetic = replayToResponse(r);
        setTrace(synthetic.trace);
        setResult(synthetic);
        setCitations(synthetic.citations);
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [onCancel],
  );

  if (!sessionId) {
    return (
      <div className="mx-auto max-w-5xl px-4 sm:px-6 py-12 text-sm" style={{ color: "var(--text-subtle)" }}>
        Initialising session…
      </div>
    );
  }

  const hasResult = !!result || trace.length > 0 || inFlight;

  return (
    <div>
      <SidebarHistory
        items={history}
        activeId={activeQueryId}
        onSelect={onSelectHistory}
        onNew={onNewQuery}
        onDelete={onDeleteHistoryItem}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Main content — pl-72 on desktop to clear the fixed sidebar */}
      <div className="md:pl-72 min-w-0">
        <div className="mx-auto max-w-3xl px-4 sm:px-8 py-8 sm:py-12 space-y-8">

          {/* Top bar (mobile menu + session actions) */}
          <div className="flex items-center justify-between gap-2">
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              className="md:hidden -ml-1 p-2 rounded hover:bg-[var(--surface-muted)]"
              aria-label="Open history"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div className="flex-1" />
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={onWipeSession}
                title="GDPR Art. 17 right-to-erasure — wipes ALL your queries from the server"
                className="hidden sm:inline-flex text-[11px] uppercase tracking-[0.1em] font-medium items-center gap-1 px-2.5 py-1.5 rounded-[3px] border transition-colors hover:border-red-300 hover:text-red-600"
                style={{ color: "var(--text-subtle)", borderColor: "transparent" }}
              >
                <Trash className="h-3 w-3" />
                <span>Erase data</span>
              </button>
              <button
                type="button"
                onClick={onNewSession}
                title="Wipe local session ID and start fresh"
                className="text-[11px] uppercase tracking-[0.1em] font-medium flex items-center gap-1 px-2.5 py-1.5 rounded-[3px] border transition-colors hover:border-[var(--border-strong)]"
                style={{ color: "var(--text-subtle)", borderColor: "transparent" }}
              >
                <RotateCcw className="h-3 w-3" />
                <span>New session</span>
              </button>
            </div>
          </div>

          {/* Hero — only when no active query */}
          {!hasResult && !replayMode && (
            <section className="space-y-3 pt-2">
              <div
                className="text-[10px] uppercase tracking-[0.18em] font-semibold"
                style={{ color: "var(--accent)" }}
              >
                Sovereign Multimodal RAG
              </div>
              <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight leading-[1.1]">
                Ask your industrial<br />
                <span style={{ color: "var(--text-muted)" }}>documentation.</span>
              </h1>
              <p className="text-[15px] leading-relaxed max-w-xl" style={{ color: "var(--text-muted)" }}>
                Multimodal retrieval over technical PDFs from Siemens, Bosch Rexroth,
                TRUMPF, KUKA, Festo, SICK and SEW Eurodrive — in German and English,
                with citations. Runs locally for full data sovereignty.
              </p>
            </section>
          )}

          {replayMode && (
            <div
              className="rounded-md border px-4 py-3 text-xs flex items-start gap-3"
              style={{
                borderColor: "var(--accent-soft)",
                background: "var(--accent-soft)",
                color: "var(--accent-fg)",
              }}
            >
              <div className="flex-1">
                <div className="font-medium">Viewing a past query from your history.</div>
                <div className="opacity-80 mt-0.5">Click <span className="font-medium">New query</span> in the sidebar to ask a fresh one.</div>
              </div>
              <button
                type="button"
                onClick={onNewQuery}
                className="text-xs font-medium flex items-center gap-1 underline-offset-2 hover:underline"
              >
                <span>New query</span>
                <ArrowRight className="h-3 w-3" />
              </button>
            </div>
          )}

          {/* Query form */}
          {!replayMode && (
            <form onSubmit={onSubmit} className="space-y-4">
              <div
                className="rounded-md border focus-within:border-[var(--foreground)] transition-colors"
                style={{ borderColor: "var(--border-strong)", background: "var(--surface)" }}
              >
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Ask in German or English…"
                  disabled={!!inFlight}
                  className="w-full px-4 py-3.5 text-[15px] bg-transparent border-none rounded-md focus:outline-none placeholder:text-[var(--text-subtle)] disabled:opacity-60"
                />
                <div
                  className="flex items-center justify-between gap-3 px-3 py-2 border-t"
                  style={{ borderColor: "var(--border)" }}
                >
                  <SovereigntyToggle value={mode} onChange={setMode} />
                  {inFlight ? (
                    <button
                      type="button"
                      onClick={onCancel}
                      className="px-4 py-1.5 rounded-md text-sm font-medium flex items-center gap-2 transition-colors"
                      style={{ background: "var(--surface-muted)", color: "var(--foreground)" }}
                    >
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      <span>Cancel</span>
                    </button>
                  ) : (
                    <button
                      type="submit"
                      disabled={!query.trim()}
                      className="px-4 py-1.5 rounded-md text-sm font-medium flex items-center gap-2 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                      style={{
                        background: "var(--foreground)",
                        color: "var(--background)",
                      }}
                    >
                      <span>Ask</span>
                      <Send className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              </div>

              <div
                className="text-[11px] font-mono"
                style={{ color: "var(--text-subtle)" }}
              >
                {mode === "local-only" && "Qwen3 4B via Ollama — $0 per query, fully on-prem"}
                {mode === "hybrid" && "Local default, API escalation when validator says complex reasoning needed"}
                {mode === "api-only" && "Claude Sonnet 4.6 / GPT-4o — fastest, logged per AI Act Art. 13"}
              </div>

              {/* Example cards */}
              {!hasResult && (
                <div className="space-y-2 pt-4">
                  <div
                    className="text-[10px] uppercase tracking-[0.14em] font-semibold"
                    style={{ color: "var(--text-subtle)" }}
                  >
                    Try
                  </div>
                  <div className="grid sm:grid-cols-2 gap-2">
                    {EXAMPLES.map((ex) => (
                      <button
                        key={ex.text}
                        type="button"
                        onClick={() => setQuery(ex.text)}
                        className="group text-left rounded-md border px-3 py-2.5 transition-all hover:border-[var(--foreground)]"
                        style={{ borderColor: "var(--border)", background: "var(--surface)" }}
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <span
                            className="text-[10px] uppercase tracking-[0.14em] font-semibold"
                            style={{ color: "var(--accent)" }}
                          >
                            {ex.brand}
                          </span>
                          <span
                            className="text-[9px] uppercase tracking-[0.1em] font-mono px-1 py-0.5 rounded-[2px]"
                            style={{
                              background: "var(--surface-muted)",
                              color: "var(--text-subtle)",
                            }}
                          >
                            {ex.lang}
                          </span>
                        </div>
                        <div className="text-[13px] leading-snug line-clamp-2" style={{ color: "var(--foreground)" }}>
                          {ex.text}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </form>
          )}

          {error && (
            <div
              className="rounded-md border px-3 py-2 text-sm"
              style={{
                borderColor: "#fca5a5",
                background: "rgba(254,202,202,0.15)",
                color: "#b91c1c",
              }}
            >
              {error}
            </div>
          )}

          {/* Agent trace */}
          {(trace.length > 0 || inFlight) && (
            <section>
              <AgentTrace trace={trace} inFlight={inFlight} />
            </section>
          )}

          {/* Answer */}
          {result && (
            <section className="space-y-2">
              <div
                className="text-[10px] uppercase tracking-[0.14em] font-semibold"
                style={{ color: "var(--text-subtle)" }}
              >
                Answer
              </div>
              <AnswerDisplay result={result} />
            </section>
          )}

          {/* Citations */}
          {citations.length > 0 && (
            <section className="space-y-2">
              <div
                className="text-[10px] uppercase tracking-[0.14em] font-semibold flex items-center justify-between"
                style={{ color: "var(--text-subtle)" }}
              >
                <span>Citations · {citations.length} sources</span>
              </div>
              <div className="grid sm:grid-cols-2 gap-2.5">
                {citations.map((c, i) => (
                  <div key={`${c.page_id}-${i}`} id={`cite-${i + 1}`}>
                    <CitationCard citation={c} rank={i + 1} />
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
