"use client";

import type { TraceEvent } from "@/lib/types";
import { Brain, Search, ShieldCheck, Sparkles, Check, type LucideIcon } from "lucide-react";

const NODE_ORDER = ["planner", "retriever", "validator", "synthesizer"];

const NODE_META: Record<string, { icon: LucideIcon; label: string; description: string }> = {
  planner: { icon: Brain, label: "Planner", description: "Decompose query, score complexity" },
  retriever: { icon: Search, label: "Retriever", description: "ColPali ANN → BGE+LoRA rerank → top-5" },
  validator: { icon: ShieldCheck, label: "Validator", description: "Coverage check, escalation decision" },
  synthesizer: { icon: Sparkles, label: "Synthesizer", description: "Cited answer via routed LLM" },
};

function formatLatency(ms: number): string {
  if (!ms) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function AgentTrace({
  trace,
  inFlight,
}: {
  trace: TraceEvent[];
  inFlight?: string | null;
}) {
  // Index completed events by step name
  const byStep = new Map<string, TraceEvent>();
  for (const ev of trace) byStep.set(ev.step, ev);

  if (trace.length === 0 && !inFlight) return null;

  return (
    <div
      className="rounded-md border overflow-hidden"
      style={{ borderColor: "var(--border)", background: "var(--surface)" }}
    >
      <div
        className="px-4 py-2.5 border-b flex items-center justify-between"
        style={{ borderColor: "var(--border)" }}
      >
        <div className="flex items-center gap-2">
          <span
            className="text-[10px] uppercase tracking-[0.14em] font-semibold"
            style={{ color: "var(--text-subtle)" }}
          >
            Agent trajectory
          </span>
        </div>
        <span className="text-[10px] font-mono tabular-nums" style={{ color: "var(--text-subtle)" }}>
          LangGraph · 4 nodes
        </span>
      </div>

      <ol className="relative px-4 py-4">
        {/* Vertical connector line */}
        <div
          className="absolute left-[26px] top-7 bottom-7 w-px"
          style={{ background: "var(--border-strong)" }}
          aria-hidden
        />

        {NODE_ORDER.map((step, idx) => {
          const ev = byStep.get(step);
          const meta = NODE_META[step];
          const Icon = meta.icon;
          const isDone = !!ev;
          const isInFlight = step === inFlight;
          const isPending = !isDone && !isInFlight;

          return (
            <li key={step} className="relative flex gap-4 pb-5 last:pb-0">
              {/* Node circle */}
              <div
                className={[
                  "relative z-10 flex-shrink-0 h-6 w-6 rounded-full border-2 flex items-center justify-center transition-all",
                  isDone ? "bg-[var(--accent)] border-[var(--accent)]" : "",
                  isInFlight ? "border-[var(--accent)] animate-pulse-soft" : "",
                  isPending ? "border-[var(--border-strong)]" : "",
                ].join(" ")}
                style={{
                  background: isDone
                    ? "var(--accent)"
                    : isInFlight
                    ? "var(--accent-soft)"
                    : "var(--surface)",
                }}
              >
                {isDone ? (
                  <Check className="h-3 w-3 text-white" strokeWidth={3} aria-hidden />
                ) : (
                  <span
                    className="text-[10px] font-mono font-semibold"
                    style={{ color: isInFlight ? "var(--accent-fg)" : "var(--text-subtle)" }}
                  >
                    {idx + 1}
                  </span>
                )}
              </div>

              {/* Node content */}
              <div className="flex-1 min-w-0 -mt-0.5">
                <div className="flex items-baseline justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Icon
                      className="h-3.5 w-3.5"
                      style={{ color: isDone || isInFlight ? "var(--accent)" : "var(--text-subtle)" }}
                      aria-hidden
                    />
                    <span
                      className="font-medium text-sm"
                      style={{
                        color: isPending ? "var(--text-subtle)" : "var(--foreground)",
                      }}
                    >
                      {meta.label}
                    </span>
                    {isInFlight && (
                      <span
                        className="text-[10px] uppercase tracking-[0.1em] font-semibold px-1.5 py-0.5 rounded-[2px]"
                        style={{ background: "var(--accent-soft)", color: "var(--accent-fg)" }}
                      >
                        running
                      </span>
                    )}
                  </div>
                  {isDone && ev?.latency_ms && (
                    <span
                      className="font-mono text-[11px] tabular-nums"
                      style={{ color: "var(--text-subtle)" }}
                    >
                      {formatLatency(ev.latency_ms)}
                    </span>
                  )}
                </div>

                <div
                  className="text-xs mt-0.5"
                  style={{
                    color: isPending ? "var(--text-subtle)" : "var(--text-muted)",
                  }}
                >
                  {ev?.detail ?? meta.description}
                </div>

                {ev?.payload && Object.keys(ev.payload).length > 0 && (
                  <details className="mt-1.5">
                    <summary
                      className="cursor-pointer text-[10px] font-mono uppercase tracking-[0.1em] select-none transition-colors hover:text-[var(--foreground)]"
                      style={{ color: "var(--text-subtle)" }}
                    >
                      payload ({Object.keys(ev.payload).length})
                    </summary>
                    <pre
                      className="mt-1.5 font-mono text-[10px] rounded-[2px] p-2 overflow-x-auto border tabular-nums leading-relaxed"
                      style={{
                        background: "var(--surface-muted)",
                        color: "var(--text-muted)",
                        borderColor: "var(--border)",
                      }}
                    >
                      {JSON.stringify(ev.payload, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
