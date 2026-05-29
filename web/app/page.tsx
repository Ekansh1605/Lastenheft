"use client";

import { useCallback, useState } from "react";
import { AgentTrace } from "@/components/agent-trace";
import { AnswerDisplay } from "@/components/answer-display";
import { CitationCard } from "@/components/citation-card";
import { SovereigntyToggle } from "@/components/sovereignty-toggle";
import { streamQuery } from "@/lib/api";
import type { Citation, QueryResponse, SovereigntyMode, TraceEvent } from "@/lib/types";
import { Send, Loader2 } from "lucide-react";

const EXAMPLES = [
  "What is the maximum sheet thickness for stainless steel on the TruLaser 2030 fiber?",
  "Welche Schutzart hat das DSBC Normzylinder?",
  "What is the operating voltage range of the IndraDrive Cs?",
  "Was sind die Anforderungen der EU-Maschinenverordnung 2023/1230 an die Risikobeurteilung?",
];

export default function Home() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SovereigntyMode>("hybrid");
  const [trace, setTrace] = useState<TraceEvent[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [inFlight, setInFlight] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [abort, setAbort] = useState<(() => void) | null>(null);

  const onSubmit = useCallback(
    (e?: React.FormEvent) => {
      e?.preventDefault();
      if (!query.trim() || inFlight) return;

      setTrace([]);
      setCitations([]);
      setResult(null);
      setError(null);
      setInFlight("planner");

      const cancel = streamQuery(query.trim(), mode, {
        onNode: (node, evs, cits) => {
          if (evs?.length) setTrace((prev) => [...prev, ...evs]);
          if (cits?.length) setCitations(cits);
          // Advance the in-flight indicator to the NEXT node
          const order = ["planner", "retriever", "validator", "synthesizer"];
          const idx = order.indexOf(node);
          setInFlight(idx >= 0 && idx + 1 < order.length ? order[idx + 1] : null);
        },
        onDone: (final) => {
          setResult(final);
          setInFlight(null);
          setAbort(null);
        },
        onError: (e) => {
          setError(e.message);
          setInFlight(null);
          setAbort(null);
        },
      });
      setAbort(() => cancel);
    },
    [query, mode, inFlight],
  );

  const onCancel = useCallback(() => {
    abort?.();
    setInFlight(null);
    setAbort(null);
  }, [abort]);

  return (
    <div className="mx-auto max-w-5xl px-4 sm:px-6 py-6 space-y-6">
      <section className="space-y-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">
            Ask your industrial documentation
          </h1>
          <p className="text-sm text-neutral-600 dark:text-neutral-400">
            Multimodal retrieval over Siemens / Bosch / TRUMPF / KUKA / Festo / SICK PDFs in
            DE + EN, with citations. Run locally for full data sovereignty.
          </p>
        </div>

        <form onSubmit={onSubmit} className="space-y-3">
          <div className="flex gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="What is the operating voltage of the IndraDrive Cs?"
              disabled={!!inFlight}
              className="flex-1 px-3 py-2 rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
            {inFlight ? (
              <button
                type="button"
                onClick={onCancel}
                className="px-4 py-2 rounded-md bg-neutral-800 text-white dark:bg-neutral-700 text-sm font-medium hover:bg-neutral-900 dark:hover:bg-neutral-600 flex items-center gap-2"
              >
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Cancel</span>
              </button>
            ) : (
              <button
                type="submit"
                disabled={!query.trim()}
                className="px-4 py-2 rounded-md bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                <Send className="h-4 w-4" />
                <span>Ask</span>
              </button>
            )}
          </div>

          <div className="flex items-center justify-between flex-wrap gap-2">
            <SovereigntyToggle value={mode} onChange={setMode} />
            <div className="text-xs text-neutral-500">
              {mode === "local-only" && "Qwen3 4B via Ollama — $0 per query"}
              {mode === "hybrid" && "Local default; API escalation when complex"}
              {mode === "api-only" && "All calls to Claude / GPT-4o"}
            </div>
          </div>

          {!result && !inFlight && (
            <div className="flex flex-wrap gap-2 pt-2">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => setQuery(ex)}
                  className="text-xs px-2 py-1 rounded border border-neutral-200 dark:border-neutral-800 hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-600 dark:text-neutral-400"
                >
                  {ex.length > 70 ? `${ex.slice(0, 70)}…` : ex}
                </button>
              ))}
            </div>
          )}
        </form>

        {error && (
          <div className="rounded border border-red-300 bg-red-50 dark:bg-red-950/30 dark:border-red-800 px-3 py-2 text-sm text-red-700 dark:text-red-300">
            {error}
          </div>
        )}
      </section>

      {(trace.length > 0 || inFlight) && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-neutral-600 dark:text-neutral-400 uppercase tracking-wide">
            Agent trace
          </h2>
          <AgentTrace trace={trace} inFlight={inFlight} />
        </section>
      )}

      {result && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-neutral-600 dark:text-neutral-400 uppercase tracking-wide">
            Answer
          </h2>
          <AnswerDisplay result={result} />
        </section>
      )}

      {citations.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-neutral-600 dark:text-neutral-400 uppercase tracking-wide">
            Citations
          </h2>
          <div className="grid sm:grid-cols-2 gap-3">
            {citations.map((c, i) => (
              <div key={c.page_id} id={`cite-${i + 1}`}>
                <CitationCard citation={c} rank={i + 1} />
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
