"use client";

import type { QueryResponse } from "@/lib/types";
import { Cpu, Cloud, ServerCog } from "lucide-react";

const PROVIDER_ICON = {
  "ollama-local": ServerCog,
  anthropic: Cloud,
  openai: Cloud,
} as const;

/**
 * Renders the answer with bracketed citations [1] [2] highlighted as pill spans.
 * Click a citation to scroll its source card into view.
 */
export function AnswerDisplay({ result }: { result: QueryResponse }) {
  const Icon = (PROVIDER_ICON as Record<string, typeof Cpu>)[result.llm_provider] ?? Cpu;
  return (
    <div className="border border-neutral-200 dark:border-neutral-800 rounded-md bg-white dark:bg-neutral-900">
      <div className="border-b border-neutral-200 dark:border-neutral-800 px-4 py-2 flex items-center justify-between text-xs text-neutral-500">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4" aria-hidden />
          <span className="font-mono">{result.llm_provider} / {result.llm_model}</span>
          {result.needs_escalation && (
            <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 text-[10px] uppercase tracking-wide font-semibold">
              escalated
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 font-mono">
          <span>{result.total_latency_ms < 1000 ? `${result.total_latency_ms}ms` : `${(result.total_latency_ms / 1000).toFixed(1)}s`}</span>
          <span>{result.input_tokens + result.output_tokens} tok</span>
          <span>${result.cost_usd.toFixed(4)}</span>
        </div>
      </div>
      <div className="p-4 text-[15px] leading-relaxed whitespace-pre-wrap">
        {renderWithCitations(result.answer)}
      </div>
    </div>
  );
}

function renderWithCitations(text: string) {
  // Replace [N] with a clickable pill
  const parts = text.split(/(\[\d+\])/g);
  return parts.map((part, i) => {
    const m = part.match(/^\[(\d+)\]$/);
    if (!m) return <span key={i}>{part}</span>;
    const rank = m[1];
    return (
      <a
        key={i}
        href={`#cite-${rank}`}
        className="inline-flex items-center justify-center min-w-[1.5rem] h-5 px-1 mx-0.5 rounded text-[11px] font-mono font-medium bg-emerald-100 text-emerald-800 hover:bg-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-300 dark:hover:bg-emerald-900/60 align-middle"
      >
        {rank}
      </a>
    );
  });
}
