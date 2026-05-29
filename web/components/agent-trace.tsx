"use client";

import type { TraceEvent } from "@/lib/types";
import { Brain, Search, ShieldCheck, Sparkles, type LucideIcon } from "lucide-react";

const ICONS: Record<string, LucideIcon> = {
  planner: Brain,
  retriever: Search,
  validator: ShieldCheck,
  synthesizer: Sparkles,
};

export function AgentTrace({
  trace,
  inFlight,
}: {
  trace: TraceEvent[];
  inFlight?: string | null;
}) {
  // Combine completed trace events with an in-flight placeholder
  const items = [...trace];
  if (inFlight && !items.find((t) => t.step === inFlight)) {
    items.push({ step: inFlight, detail: "running…", latency_ms: 0, payload: {} });
  }
  if (items.length === 0) return null;

  return (
    <ol className="space-y-2">
      {items.map((ev, i) => {
        const Icon = ICONS[ev.step] ?? Brain;
        const running = ev.step === inFlight && ev.detail === "running…";
        return (
          <li
            key={`${ev.step}-${i}`}
            className={[
              "flex items-start gap-3 rounded border px-3 py-2 text-sm",
              running
                ? "border-emerald-300 bg-emerald-50 dark:bg-emerald-950/30 dark:border-emerald-800 animate-pulse-soft"
                : "border-neutral-200 bg-white dark:bg-neutral-900 dark:border-neutral-800",
            ].join(" ")}
          >
            <Icon className="h-4 w-4 mt-0.5 text-neutral-500 flex-shrink-0" aria-hidden />
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium capitalize">{ev.step}</span>
                {ev.latency_ms > 0 && (
                  <span className="font-mono text-xs text-neutral-500">
                    {ev.latency_ms < 1000
                      ? `${ev.latency_ms}ms`
                      : `${(ev.latency_ms / 1000).toFixed(1)}s`}
                  </span>
                )}
              </div>
              <div className="text-neutral-600 dark:text-neutral-400 text-xs mt-0.5 break-words">
                {ev.detail}
              </div>
              {ev.payload && Object.keys(ev.payload).length > 0 && (
                <details className="mt-1 text-xs">
                  <summary className="cursor-pointer text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-300 select-none">
                    payload
                  </summary>
                  <pre className="mt-1 font-mono text-[11px] text-neutral-600 dark:text-neutral-400 bg-neutral-50 dark:bg-neutral-950 rounded p-2 overflow-x-auto">
                    {JSON.stringify(ev.payload, null, 2)}
                  </pre>
                </details>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
