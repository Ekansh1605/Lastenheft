"use client";

import type { SovereigntyMode } from "@/lib/types";
import { ShieldCheck, Shuffle, Cloud } from "lucide-react";

const MODES: { value: SovereigntyMode; label: string; icon: typeof ShieldCheck; hint: string }[] =
  [
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
    <div className="inline-flex rounded-md border border-neutral-200 dark:border-neutral-700 overflow-hidden text-sm">
      {MODES.map((m) => {
        const Icon = m.icon;
        const active = m.value === value;
        return (
          <button
            key={m.value}
            type="button"
            onClick={() => onChange(m.value)}
            title={m.hint}
            className={[
              "flex items-center gap-1.5 px-3 py-1.5 transition-colors",
              active
                ? "bg-neutral-900 text-white dark:bg-white dark:text-neutral-900"
                : "bg-white hover:bg-neutral-50 dark:bg-neutral-900 dark:hover:bg-neutral-800",
            ].join(" ")}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden />
            <span>{m.label}</span>
          </button>
        );
      })}
    </div>
  );
}
