"use client";

import { useMemo, useState } from "react";
import type { HistoryItem } from "@/lib/types";
import {
  MessageSquare, Plus, ServerCog, Cloud, Shuffle, Trash2, X, Inbox,
  type LucideIcon,
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

function dayBucket(iso: string): "Today" | "Yesterday" | "Earlier" {
  const t = new Date(iso);
  const now = new Date();
  const sameDay = t.toDateString() === now.toDateString();
  if (sameDay) return "Today";
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (t.toDateString() === yesterday.toDateString()) return "Yesterday";
  return "Earlier";
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

  // Group by Today / Yesterday / Earlier
  const grouped = useMemo(() => {
    const map = new Map<string, HistoryItem[]>();
    for (const it of items) {
      const b = dayBucket(it.created_at);
      if (!map.has(b)) map.set(b, []);
      map.get(b)!.push(it);
    }
    return Array.from(map.entries());
  }, [items]);

  return (
    <>
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
          "w-72 flex-shrink-0 border-r flex flex-col",
          // Desktop: pinned to the viewport below the fixed 64px header
          "md:fixed md:left-0 md:top-16 md:bottom-0 md:h-[calc(100vh-4rem)] md:z-30",
          // Mobile: full-height drawer that slides in from the left
          "fixed top-0 left-0 h-full z-40 transition-transform duration-200",
          open ? "translate-x-0" : "-translate-x-full md:translate-x-0",
        ].join(" ")}
        style={{ background: "var(--surface)", borderColor: "var(--border)" }}
      >
        {/* Header / New query button */}
        <div className="p-3 border-b flex items-center gap-2" style={{ borderColor: "var(--border)" }}>
          <button
            type="button"
            onClick={onNew}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors"
            style={{
              background: "var(--foreground)",
              color: "var(--background)",
            }}
          >
            <Plus className="h-4 w-4" />
            <span>New query</span>
          </button>
          <button
            type="button"
            onClick={onClose}
            className="md:hidden p-2 rounded hover:bg-[var(--surface-muted)]"
            aria-label="Close history"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* History list */}
        <div className="flex-1 overflow-y-auto py-2">
          {items.length === 0 && (
            <div className="px-4 py-12 text-center space-y-3">
              <div
                className="inline-flex h-10 w-10 items-center justify-center rounded-full mx-auto"
                style={{ background: "var(--surface-muted)" }}
              >
                <Inbox className="h-5 w-5" style={{ color: "var(--text-subtle)" }} aria-hidden />
              </div>
              <div>
                <div className="text-xs font-medium" style={{ color: "var(--foreground)" }}>
                  No queries yet
                </div>
                <div className="text-[11px] mt-0.5" style={{ color: "var(--text-subtle)" }}>
                  Ask something to start your session.
                </div>
              </div>
            </div>
          )}

          {grouped.map(([bucket, group]) => (
            <div key={bucket} className="px-2 mb-3">
              <div
                className="px-2 py-1.5 text-[10px] uppercase tracking-[0.14em] font-semibold"
                style={{ color: "var(--text-subtle)" }}
              >
                {bucket}
              </div>
              <div className="space-y-0.5">
                {group.map((it) => {
                  const Icon = MODE_ICON[it.sovereignty_mode] ?? MessageSquare;
                  const active = activeId === it.id;
                  const confirming = confirmingDelete === it.id;
                  return (
                    <div
                      key={it.id}
                      className="group relative rounded-md transition-colors"
                      style={{
                        background: active ? "var(--accent-soft)" : "transparent",
                        border: `1px solid ${active ? "var(--accent)" : "transparent"}`,
                      }}
                    >
                      <button
                        type="button"
                        onClick={() => onSelect(it.id)}
                        className="w-full text-left rounded-md px-2.5 py-2 hover:bg-[var(--surface-muted)]"
                        style={{ background: active ? "transparent" : undefined }}
                      >
                        <div className="flex items-start gap-2">
                          <Icon
                            className="h-3.5 w-3.5 mt-0.5 flex-shrink-0"
                            style={{ color: active ? "var(--accent)" : "var(--text-subtle)" }}
                            aria-hidden
                          />
                          <div className="min-w-0 flex-1 pr-5">
                            <div
                              className="text-sm line-clamp-2 leading-snug"
                              style={{ color: "var(--foreground)" }}
                            >
                              {it.user_query}
                            </div>
                            <div
                              className="text-[10px] mt-1 flex items-center gap-1.5 font-mono tabular-nums"
                              style={{ color: "var(--text-subtle)" }}
                            >
                              <span>{relativeTime(it.created_at)}</span>
                              {it.cost_usd > 0 ? (
                                <span>· ${it.cost_usd.toFixed(4)}</span>
                              ) : (
                                <span>· free</span>
                              )}
                            </div>
                          </div>
                        </div>
                      </button>

                      {confirming ? (
                        <div
                          className="absolute top-1 right-1 flex items-center gap-1 rounded-[3px] px-1.5 py-0.5 border"
                          style={{
                            background: "var(--surface)",
                            borderColor: "#ef4444",
                          }}
                        >
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onDelete(it.id);
                              setConfirmingDelete(null);
                            }}
                            className="text-[11px] font-medium hover:underline"
                            style={{ color: "#dc2626" }}
                          >
                            delete?
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setConfirmingDelete(null);
                            }}
                            className="text-[11px]"
                            style={{ color: "var(--text-subtle)" }}
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
                          className="absolute top-1.5 right-1.5 p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                          style={{ color: "var(--text-subtle)" }}
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Footer count — height matched to the right footer's bottom strip
            (py-3) so the two read as one continuous bar across the bottom. */}
        {items.length > 0 && (
          <div
            className="border-t px-4 py-3 text-[10px] font-mono tabular-nums flex items-center justify-between"
            style={{ borderColor: "var(--border)", color: "var(--text-subtle)" }}
          >
            <span>{items.length} {items.length === 1 ? "query" : "queries"}</span>
            <span>this session</span>
          </div>
        )}
      </aside>
    </>
  );
}
