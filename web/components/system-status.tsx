"use client";

import { useEffect, useState } from "react";

type Status = "ok" | "degraded" | "down" | "checking";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

const STATUS_COLOR: Record<Status, string> = {
  ok: "#10b981",
  degraded: "#f59e0b",
  down: "#ef4444",
  checking: "#a8a29e",
};
const STATUS_LABEL: Record<Status, string> = {
  ok: "Backend ready",
  degraded: "Backend degraded",
  down: "Backend offline",
  checking: "Checking…",
};

export function SystemStatus() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const r = await fetch(`${API_BASE}/readyz`, { cache: "no-store" });
        if (!alive) return;
        if (r.ok) {
          const body = await r.json();
          setStatus(body.status === "ok" ? "ok" : "degraded");
        } else {
          setStatus("degraded");
        }
      } catch {
        if (alive) setStatus("down");
      }
    };
    check();
    const id = setInterval(check, 30_000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div
      title={STATUS_LABEL[status]}
      className="hidden sm:flex items-center gap-1.5 px-2 py-1 rounded-[3px] border"
      style={{ borderColor: "var(--border)" }}
    >
      <span className="relative inline-flex h-1.5 w-1.5">
        <span
          className="absolute inline-flex h-full w-full rounded-full opacity-60 animate-ping"
          style={{ background: STATUS_COLOR[status] }}
        />
        <span
          className="relative inline-flex h-1.5 w-1.5 rounded-full"
          style={{ background: STATUS_COLOR[status] }}
        />
      </span>
      <span
        className="text-[10px] uppercase tracking-[0.1em] font-medium"
        style={{ color: "var(--text-muted)" }}
      >
        {status === "checking" ? "checking" : status === "ok" ? "online" : status}
      </span>
    </div>
  );
}
