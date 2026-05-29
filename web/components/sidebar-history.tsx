"use client";

import { useState } from "react";
import type { HistoryItem } from "@/lib/types";
import {
  MessageSquare, Plus, ServerCog, Cloud, Shuffle, Trash2, X, type LucideIcon,
} from "lucide-react";

const MODE_ICON: Record<string, LucideIcon> = {
  "local-only": ServerCog,
  hybrid: Shuffle,
  "api-only": Cloud,
};

function relativeTime(iso: string): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const diffSec = Math.max(0, (Date.now() - t) / 1000);
  if (diffSec < 60) return `${Math.round(diffSec)}s ago`;
  if (diffSec < 3600) return `${Math.round(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.round(diffSec / 3600)}h ago`;
  return `${Math.round(diffSec / 86400)}d ago`;
}

export function SidebarHistory({
  items,
  activeId,
  onSelect,
  onNew,
  onDelete,
  open,
  onClose,
}: {
  items: HistoryItem[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  open: boolean;
  onClose: () => void;
}) {
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null);

  return (
    <>
      {/* Mobile backdrop */}
      {open && (
        <button
          type="button"
          aria-label="Close history"
          onClick={onClose}
          className="md:hidden fixed inset-0 z-30 bg-black/40"
        />
      )}

      <aside
        className={[
          "w-64 flex-shrink-0 border-r border-neutral-200 dark:border-neutral-800",
          "bg-white dark:bg-neutral-900 flex flex-col",
          // Desktop: in-flow sticky sidebar
          "md:sticky md:top-14 md:h-[calc(100vh-3.5rem-2.5rem)]",
          // Mobile: fixed drawer that slides in
          "fixed top-0 left-0 h-full z-40 transition-transform duration-200",
          open ? "translate-x-0" : "-translate-x-full md:translate-x-0",
        ].join(" ")}
      >
        <div className="p-3 border-b border-neutral-200 dark:border-neutral-800 flex items-center gap-2">
          <button
            type="button"
            onClick={onNew}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-md border border-dashed border-neutral-300 dark:border-neutral-700 text-sm font-medium hover:bg-neutral-50 dark:hover:bg-neutral-800"
          >
            <Plus className="h-4 w-4" />
            <span>New query</span>
          </button>
          <button
            type="button"
            onClick={onClose}
            className="md:hidden p-2 rounded hover:bg-neutral-100 dark:hover:bg-neutral-800"
            aria-label="Close history"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {items.length === 0 && (
            <div className="text-xs text-neutral-500 px-2 py-4 text-center">
              No queries yet. Ask something to start your session history.
            </div>
          )}
          {items.map((it) => {
            const Icon = MODE_ICON[it.sovereignty_mode] ?? MessageSquare;
            const active = activeId === it.id;
            const confirming = confirmingDelete === it.id;
            return (
              <div
                key={it.id}
                className={[
                  "rounded-md text-sm transition-colors group relative",
                  active
                    ? "bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800"
                    : "border border-transparent hover:bg-neutral-50 dark:hover:bg-neutral-800",
                ].join(" ")}
              >
                <button
                  type="button"
                  onClick={() => onSelect(it.id)}
                  className="w-full text-left rounded-md px-2.5 py-2"
                >
                  <div className="flex items-start gap-2">
                    <Icon className="h-3.5 w-3.5 mt-0.5 flex-shrink-0 text-neutral-500" aria-hidden />
                    <div className="min-w-0 flex-1 pr-6">
                      <div className="line-clamp-2 text-neutral-800 dark:text-neutral-200">
                        {it.user_query}
                      </div>
                      <div className="text-[11px] text-neutral-500 mt-0.5 flex items-center gap-1.5 font-mono">
                        <span>{relativeTime(it.created_at)}</span>
                        {it.cost_usd > 0 ? <span>• ${it.cost_usd.toFixed(4)}</span> : <span>• free</span>}
                      </div>
                    </div>
                  </div>
                </button>
                {confirming ? (
                  <div className="absolute top-1 right-1 flex items-center gap-1 bg-white dark:bg-neutral-900 border border-red-300 dark:border-red-800 rounded px-1.5 py-0.5">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete(it.id);
                        setConfirmingDelete(null);
                      }}
                      className="text-[11px] text-red-600 hover:text-red-700 font-medium"
                    >
                      delete?
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setConfirmingDelete(null);
                      }}
                      className="text-[11px] text-neutral-500 hover:text-neutral-700"
                    >
                      cancel
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    aria-label="Delete query"
                    onClick={(e) => {
                      e.stopPropagation();
                      setConfirmingDelete(it.id);
                    }}
                    className="absolute top-1.5 right-1.5 p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-red-100 dark:hover:bg-red-950/40 text-neutral-400 hover:text-red-600 transition-opacity"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </aside>
    </>
  );
}
