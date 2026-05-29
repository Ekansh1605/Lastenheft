"use client";

import type { Citation } from "@/lib/types";
import { FileText } from "lucide-react";

export function CitationCard({ citation, rank }: { citation: Citation; rank: number }) {
  // Pull brand from filename like "trumpf-trulaser-2030-..." -> "trumpf"
  const brand = (citation.filename.split("-")[0] || "doc").toUpperCase();
  return (
    <div className="border border-neutral-200 dark:border-neutral-800 rounded-md p-3 bg-white dark:bg-neutral-900 flex flex-col gap-2">
      <div className="flex items-start gap-2">
        <div className="font-mono text-xs px-1.5 py-0.5 rounded bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300">
          [{rank}]
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-xs text-neutral-500">
            <span className="font-semibold text-neutral-700 dark:text-neutral-300">{brand}</span>
            <span>•</span>
            <span>page {citation.page_number}</span>
            <span>•</span>
            <span className="font-mono">score {citation.score.toFixed(2)}</span>
          </div>
          <div className="text-xs text-neutral-600 dark:text-neutral-400 truncate" title={citation.filename}>
            <FileText className="inline h-3 w-3 mr-1 -mt-0.5" aria-hidden />
            {citation.filename}
          </div>
        </div>
      </div>
      {citation.snippet && (
        <p className="text-xs text-neutral-700 dark:text-neutral-300 leading-relaxed line-clamp-4">
          {citation.snippet}
        </p>
      )}
    </div>
  );
}
