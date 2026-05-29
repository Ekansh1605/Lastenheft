"use client";

import type { QueryResponse } from "@/lib/types";
import { Cloud, ServerCog, Cpu, type LucideIcon } from "lucide-react";

const PROVIDER_ICON: Record<string, LucideIcon> = {
  "ollama-local": ServerCog,
  anthropic: Cloud,
  openai: Cloud,
};

const PROVIDER_LABEL: Record<string, string> = {
  "ollama-local": "On-prem",
  anthropic: "Anthropic API",
  openai: "OpenAI API",
};

function formatLatency(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function AnswerDisplay({ result }: { result: QueryResponse }) {
  const Icon = PROVIDER_ICON[result.llm_provider] ?? Cpu;
  const providerLabel = PROVIDER_LABEL[result.llm_provider] ?? result.llm_provider;
  const totalTokens = result.input_tokens + result.output_tokens;
  const isLocal = result.llm_provider === "ollama-local";

  return (
    <div
      className="rounded-md border overflow-hidden"
      style={{ borderColor: "var(--border)", background: "var(--surface)" }}
    >
      {/* Provider strip */}
      <div
        className="px-4 py-2.5 border-b flex items-center justify-between flex-wrap gap-2"
        style={{ borderColor: "var(--border)", background: "var(--surface-muted)" }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <Icon
            className="h-3.5 w-3.5 flex-shrink-0"
            style={{ color: isLocal ? "var(--accent)" : "var(--text-muted)" }}
            aria-hidden
          />
          <span className="text-xs font-medium" style={{ color: "var(--foreground)" }}>
            {providerLabel}
          </span>
          <span className="text-xs font-mono truncate" style={{ color: "var(--text-subtle)" }}>
            {result.llm_model}
          </span>
          {result.needs_escalation && (
            <span
              className="ml-1 inline-flex items-center px-1.5 py-0.5 rounded-[2px] text-[10px] uppercase tracking-[0.1em] font-semibold"
              style={{ background: "rgba(245,158,11,0.15)", color: "#b45309" }}
            >
              escalated
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 sm:gap-4 text-[11px] font-mono tabular-nums" style={{ color: "var(--text-muted)" }}>
          <span title="Total wall-clock time">{formatLatency(result.total_latency_ms)}</span>
          <span
            className="hidden sm:inline-block w-px h-3"
            style={{ background: "var(--border)" }}
            aria-hidden
          />
          <span title="Input + output tokens">{totalTokens.toLocaleString()} tok</span>
          <span
            className="hidden sm:inline-block w-px h-3"
            style={{ background: "var(--border)" }}
            aria-hidden
          />
          <span
            title={isLocal ? "Local inference — no API cost" : "API cost in USD"}
            style={{ color: isLocal ? "var(--accent)" : "var(--text-muted)" }}
          >
            {isLocal ? "$0.0000" : `$${result.cost_usd.toFixed(4)}`}
          </span>
        </div>
      </div>

      {/* Answer body */}
      <div className="p-5 text-[15px] leading-[1.7] whitespace-pre-wrap" style={{ color: "var(--foreground)" }}>
        {renderWithCitations(result.answer)}
      </div>

      {/* Confidence footer */}
      {result.confidence > 0 && (
        <div
          className="px-4 py-2 border-t flex items-center justify-between gap-3 text-[11px]"
          style={{ borderColor: "var(--border)" }}
        >
          <span className="font-mono uppercase tracking-[0.1em]" style={{ color: "var(--text-subtle)" }}>
            Coverage confidence
          </span>
          <div className="flex items-center gap-2 flex-1 max-w-[200px]">
            <div
              className="relative flex-1 h-1 rounded-full overflow-hidden"
              style={{ background: "var(--surface-muted)" }}
            >
              <div
                className="absolute inset-y-0 left-0 transition-all"
                style={{
                  width: `${result.confidence * 100}%`,
                  background:
                    result.confidence >= 0.7
                      ? "var(--accent)"
                      : result.confidence >= 0.4
                      ? "#f59e0b"
                      : "#ef4444",
                }}
              />
            </div>
            <span className="font-mono tabular-nums" style={{ color: "var(--text-muted)" }}>
              {(result.confidence * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function renderWithCitations(text: string) {
  const parts = text.split(/(\[\d+\])/g);
  return parts.map((part, i) => {
    const m = part.match(/^\[(\d+)\]$/);
    if (!m) return <span key={i}>{part}</span>;
    const rank = m[1];
    return (
      <a
        key={i}
        href={`#cite-${rank}`}
        className="inline-flex items-center justify-center min-w-[1.5rem] h-5 px-1 mx-0.5 rounded-[3px] text-[11px] font-mono font-semibold tabular-nums transition-colors align-baseline hover:scale-110"
        style={{
          background: "var(--accent-soft)",
          color: "var(--accent-fg)",
        }}
        title={`Jump to source ${rank}`}
      >
        {rank}
      </a>
    );
  });
}
