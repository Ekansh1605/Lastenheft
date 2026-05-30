"use client";

import type { SovereigntyMode } from "@/lib/types";
import { ShieldCheck, Shuffle, Cloud } from "lucide-react";

const MODES: { value: SovereigntyMode; label: string; icon: typeof ShieldCheck; hint: string }[] = [
  {
    value: "local-only",
    label: "Sovereign",
    icon: ShieldCheck,
    hint: "Qwen3 4B on-prem. Nothing leaves your hardware.",
  },
  {
    value: "hybrid",
    label: "Hybrid",
    icon: Shuffle,
    hint: "Local by default, API for complex reasoning. Logged per AI Act Art. 13.",
  },
  {
    value: "api-only",
    label: "API",
    icon: Cloud,
    hint: "Claude / GPT-4o for every call. Fastest, not sovereign.",
  },
];

export function SovereigntyToggle({
  value,
  onChange,
}: {
  value: SovereigntyMode;
  onChange: (m: SovereigntyMode) => void;
}) {
  return (
    <div
      role="radiogroup"
      aria-label="Sovereignty mode"
      className="inline-flex rounded-md border overflow-hidden text-sm"
      style={{ borderColor: "var(--border-strong)", background: "var(--surface)" }}
    >
      {MODES.map((m, i) => {
        const Icon = m.icon;
        const active = m.value === value;
        return (
          <button
            key={m.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(m.value)}
            title={m.hint}
            className={[
              "group flex items-center gap-1.5 px-3 py-1.5 relative cursor-pointer",
              "transition-all duration-150 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent)] focus-visible:z-10",
              !active ? "hover:bg-[var(--surface-muted)] hover:text-[var(--foreground)]" : "",
              i > 0 ? "border-l" : "",
            ].join(" ")}
            style={{
              borderLeftColor: "var(--border-strong)",
              background: active ? "var(--foreground)" : "transparent",
              color: active ? "var(--background)" : "var(--text-muted)",
              fontWeight: active ? 600 : 500,
            }}
          >
            <Icon
              className={[
                "h-3.5 w-3.5 transition-transform",
                !active ? "group-hover:scale-110" : "",
              ].join(" ")}
              aria-hidden
            />
            <span>{m.label}</span>
            {/* Active indicator dot under the label for selected state */}
            {active && (
              <span
                aria-hidden
                className="absolute bottom-0.5 left-1/2 -translate-x-1/2 h-[2px] w-3 rounded-full"
                style={{ background: "var(--accent)" }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
