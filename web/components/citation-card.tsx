"use client";

import type { Citation } from "@/lib/types";
import { FileText } from "lucide-react";

// Mittelstand brand-color hints — used as a left-edge accent strip on each
// citation card so the eye can pick out cross-brand answers at a glance.
const BRAND_ACCENT: Record<string, string> = {
  siemens: "#009999",       // SIMATIC teal
  bosch: "#dd2a1b",         // Bosch red
  trumpf: "#005ca9",        // TRUMPF blue
  kuka: "#ff6600",          // KUKA orange
  festo: "#0066cc",         // Festo blue
  sick: "#1c75bc",          // SICK blue
  sew: "#009639",           // SEW Eurodrive green
  eu: "#003399",            // EU blue
};

function brandFromFilename(filename: string): { tag: string; color: string } {
  const first = (filename.split("-")[0] || "doc").toLowerCase();
  return { tag: first.toUpperCase(), color: BRAND_ACCENT[first] ?? "#78716c" };
}

export function CitationCard({ citation, rank }: { citation: Citation; rank: number }) {
  const { tag, color } = brandFromFilename(citation.filename);
  return (
    <article
      className="group relative rounded-md border overflow-hidden transition-all hover:border-[var(--border-strong)] hover:shadow-sm"
      style={{ borderColor: "var(--border)", background: "var(--surface)" }}
    >
      {/* Brand color stripe on the left */}
      <div
        className="absolute top-0 bottom-0 left-0 w-[3px]"
        style={{ background: color }}
        aria-hidden
      />

      <div className="pl-4 pr-3.5 py-3 space-y-2">
        {/* Header row */}
        <div className="flex items-start gap-2.5">
          <span
            className="flex-shrink-0 inline-flex items-center justify-center h-6 min-w-[1.5rem] px-1.5 rounded-[3px] text-[11px] font-mono font-semibold tabular-nums"
            style={{ background: "var(--surface-muted)", color: "var(--foreground)" }}
          >
            {rank}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline gap-1.5 flex-wrap">
              <span
                className="text-[10px] uppercase tracking-[0.14em] font-semibold"
                style={{ color }}
              >
                {tag}
              </span>
              <span
                className="text-[11px] font-mono tabular-nums"
                style={{ color: "var(--text-subtle)" }}
              >
                p. {citation.page_number}
              </span>
              <span style={{ color: "var(--text-subtle)" }}>·</span>
              <span
                className="text-[11px] font-mono tabular-nums"
                style={{ color: "var(--text-subtle)" }}
                title="Reranker score (higher = more relevant)"
              >
                score {citation.score.toFixed(2)}
              </span>
            </div>
            <div
              className="text-[11px] mt-0.5 truncate flex items-center gap-1"
              style={{ color: "var(--text-muted)" }}
              title={citation.filename}
            >
              <FileText className="h-3 w-3 flex-shrink-0" aria-hidden />
              <span className="truncate font-mono">{citation.filename}</span>
            </div>
          </div>
        </div>

        {/* Snippet */}
        {citation.snippet && (
          <p
            className="text-[12.5px] leading-relaxed line-clamp-4 pl-[34px]"
            style={{ color: "var(--text-muted)" }}
          >
            {citation.snippet}
          </p>
        )}
      </div>
    </article>
  );
}
