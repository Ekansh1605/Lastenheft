import { fetchAuditLog, fetchRiskClassifications } from "@/lib/api";
import type { AuditEvent } from "@/lib/types";
import { Activity, Shield, FileText, Server, AlertCircle } from "lucide-react";

const CATEGORY_STYLE: Record<string, { bg: string; fg: string; label: string }> = {
  minimal: { bg: "rgba(16,185,129,0.12)", fg: "#047857", label: "Minimal Risk" },
  limited: { bg: "rgba(59,130,246,0.12)", fg: "#1d4ed8", label: "Limited Risk" },
  high: { bg: "rgba(245,158,11,0.15)", fg: "#b45309", label: "High Risk" },
  unacceptable: { bg: "rgba(239,68,68,0.15)", fg: "#b91c1c", label: "Unacceptable" },
};

const EVENT_COLOR: Record<string, string> = {
  planner: "#8b5cf6",
  retriever: "#3b82f6",
  validator: "#f59e0b",
  synthesizer: "#10b981",
};

function asNum(x: number | string | null | undefined): number | null {
  if (x === null || x === undefined) return null;
  const n = typeof x === "number" ? x : Number(x);
  return Number.isFinite(n) ? n : null;
}
function fmtCost(c: number | string | null): string {
  const n = asNum(c);
  if (!n) return "—";
  return `$${n.toFixed(4)}`;
}
function fmtLatency(ms: number | string | null): string {
  const n = asNum(ms);
  if (!n) return "—";
  if (n < 1000) return `${n}ms`;
  return `${(n / 1000).toFixed(1)}s`;
}
function fmtTokens(tin: number | string | null, tout: number | string | null): string {
  const ni = asNum(tin), no = asNum(tout);
  if (!ni && !no) return "—";
  return `${ni ?? 0} / ${no ?? 0}`;
}

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function CompliancePage() {
  let classifications: Awaited<ReturnType<typeof fetchRiskClassifications>> = [];
  let audit: { events: AuditEvent[]; total: number } = { events: [], total: 0 };
  let unreachable = false;

  try {
    classifications = await fetchRiskClassifications();
    audit = await fetchAuditLog(100);
  } catch {
    unreachable = true;
  }

  // Aggregate stats from audit
  const totalCost = audit.events.reduce((s, e) => s + (asNum(e.cost_usd) ?? 0), 0);
  const totalLatency = audit.events.reduce((s, e) => s + (asNum(e.latency_ms) ?? 0), 0);
  const avgLatency = audit.events.length > 0 ? Math.round(totalLatency / audit.events.length) : 0;
  const uniqueSessions = new Set(audit.events.map((e) => e.session_id)).size;

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-8 py-8 sm:py-10 space-y-10">

      {/* Page header */}
      <section className="space-y-2">
        <div
          className="text-[10px] uppercase tracking-[0.18em] font-semibold"
          style={{ color: "var(--accent)" }}
        >
          EU AI Act Compliance
        </div>
        <h1 className="text-3xl font-semibold tracking-tight">
          Designed in, not bolted on.
        </h1>
        <p className="text-sm max-w-2xl" style={{ color: "var(--text-muted)" }}>
          Risk classification per Article 6. Transparency obligations per Article 13.
          GDPR Article 17 right-to-erasure built in. Every agent step persisted
          with provider, model, tokens, cost, and latency.
        </p>
      </section>

      {/* Status banner */}
      {unreachable && (
        <div
          className="rounded-md border px-4 py-3 flex items-start gap-3"
          style={{ borderColor: "#f59e0b", background: "rgba(245,158,11,0.08)" }}
        >
          <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" style={{ color: "#b45309" }} aria-hidden />
          <div className="text-sm" style={{ color: "#b45309" }}>
            Backend at <code className="font-mono">http://127.0.0.1:8000</code> is not reachable.
            Start it with <code className="font-mono">uvicorn api.main:app --reload</code>.
          </div>
        </div>
      )}

      {/* Stats strip */}
      {!unreachable && (
        <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard icon={Activity} label="Audit events" value={audit.total.toLocaleString()} hint="all sessions" />
          <StatCard icon={FileText} label="Avg latency" value={fmtLatency(avgLatency)} hint="per node, last 100" />
          <StatCard icon={Server} label="Cost (last 100)" value={`$${totalCost.toFixed(4)}`} hint="LLM API spend" />
          <StatCard icon={Shield} label="Sessions" value={uniqueSessions.toString()} hint="distinct users" />
        </section>
      )}

      {/* Risk classifications */}
      <section className="space-y-3">
        <SectionHeader
          eyebrow="Article 6"
          title="Risk classification"
          hint="Self-classified on first DB init. Source of truth: risk_classifications table."
        />
        {!unreachable && (
          <div className="grid md:grid-cols-3 gap-3">
            {classifications.map((c) => {
              const style = CATEGORY_STYLE[c.category] ?? CATEGORY_STYLE.limited;
              return (
                <div
                  key={c.component}
                  className="rounded-md border p-4 space-y-3 flex flex-col"
                  style={{ borderColor: "var(--border)", background: "var(--surface)" }}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="font-semibold capitalize" style={{ color: "var(--foreground)" }}>
                      {c.component.replace("-", " ")}
                    </div>
                    <span
                      className="text-[10px] uppercase tracking-[0.1em] font-bold px-2 py-1 rounded-[3px] flex-shrink-0"
                      style={{ background: style.bg, color: style.fg }}
                    >
                      {style.label}
                    </span>
                  </div>
                  <div
                    className="text-[10px] uppercase tracking-[0.1em] font-mono"
                    style={{ color: "var(--text-subtle)" }}
                  >
                    {c.article_refs.join(" · ")}
                  </div>
                  <p className="text-[13px] leading-relaxed flex-1" style={{ color: "var(--text-muted)" }}>
                    {c.rationale}
                  </p>
                  {c.mitigations.length > 0 && (
                    <div className="pt-2 border-t space-y-1" style={{ borderColor: "var(--border)" }}>
                      <div
                        className="text-[10px] uppercase tracking-[0.14em] font-semibold"
                        style={{ color: "var(--text-subtle)" }}
                      >
                        Mitigations
                      </div>
                      <ul className="text-[12px] space-y-0.5" style={{ color: "var(--text-muted)" }}>
                        {c.mitigations.map((m, i) => (
                          <li key={i} className="flex gap-1.5">
                            <span style={{ color: "var(--accent)" }}>·</span>
                            <span>{m}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Article 13 obligations */}
      <section className="space-y-3">
        <SectionHeader
          eyebrow="Article 13"
          title="Transparency obligations"
          hint="Surfaced in the UI on every answer; persisted to audit_events."
        />
        <div
          className="rounded-md border p-5"
          style={{ borderColor: "var(--border)", background: "var(--surface)" }}
        >
          <ul className="grid sm:grid-cols-2 gap-x-6 gap-y-2 text-sm" style={{ color: "var(--text-muted)" }}>
            {[
              "LLM provider + model surfaced on every answer (top-right of card)",
              "Source citations on every fact (bracketed [N] pills in the answer)",
              "Routing decisions logged with timestamp + cost",
              "Coverage confidence + escalation flag exposed to user",
              "Audit trail: provider, model, tokens, cost, latency per node",
              "GDPR Art. 17: per-query and per-session right-to-erasure",
            ].map((it) => (
              <li key={it} className="flex items-start gap-2">
                <span
                  className="inline-block h-1 w-1 rounded-full mt-2 flex-shrink-0"
                  style={{ background: "var(--accent)" }}
                  aria-hidden
                />
                <span>{it}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Audit log */}
      <section className="space-y-3">
        <SectionHeader
          eyebrow="Real-time"
          title="Audit log"
          hint={audit.events.length > 0 ? `${audit.events.length} of ${audit.total.toLocaleString()} events shown` : "Empty for now"}
        />
        {audit.events.length === 0 ? (
          <div
            className="rounded-md border p-10 text-center"
            style={{ borderColor: "var(--border)", background: "var(--surface)" }}
          >
            <div
              className="inline-flex h-12 w-12 items-center justify-center rounded-full mx-auto mb-3"
              style={{ background: "var(--surface-muted)" }}
            >
              <Activity className="h-5 w-5" style={{ color: "var(--text-subtle)" }} aria-hidden />
            </div>
            <div className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
              No audit events yet
            </div>
            <div className="text-xs mt-1" style={{ color: "var(--text-subtle)" }}>
              Run a query on the <a href="/" className="underline" style={{ color: "var(--accent)" }}>Ask</a> page — each
              one writes 4 rows (one per agent node) to <code className="font-mono">audit_events</code>.
            </div>
          </div>
        ) : (
          <div
            className="rounded-md border overflow-hidden"
            style={{ borderColor: "var(--border)", background: "var(--surface)" }}
          >
            <div className="overflow-x-auto">
              <table className="w-full text-[12px] tabular-nums">
                <thead style={{ background: "var(--surface-muted)" }}>
                  <tr style={{ color: "var(--text-subtle)" }}>
                    <th className="text-left font-medium uppercase tracking-[0.1em] text-[10px] px-3 py-2.5">Time</th>
                    <th className="text-left font-medium uppercase tracking-[0.1em] text-[10px] px-3 py-2.5">Node</th>
                    <th className="text-left font-medium uppercase tracking-[0.1em] text-[10px] px-3 py-2.5">Provider</th>
                    <th className="text-left font-medium uppercase tracking-[0.1em] text-[10px] px-3 py-2.5">Model</th>
                    <th className="text-right font-medium uppercase tracking-[0.1em] text-[10px] px-3 py-2.5">Tok (in/out)</th>
                    <th className="text-right font-medium uppercase tracking-[0.1em] text-[10px] px-3 py-2.5">Cost</th>
                    <th className="text-right font-medium uppercase tracking-[0.1em] text-[10px] px-3 py-2.5">Latency</th>
                  </tr>
                </thead>
                <tbody>
                  {audit.events.map((e, i) => (
                    <tr
                      key={e.id}
                      className="border-t hover:bg-[var(--surface-muted)] transition-colors"
                      style={{
                        borderColor: "var(--border)",
                        background: i % 2 === 0 ? "var(--surface)" : "transparent",
                      }}
                    >
                      <td className="px-3 py-2 font-mono" style={{ color: "var(--text-subtle)" }}>
                        {new Date(e.created_at).toLocaleTimeString()}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className="inline-flex items-center gap-1.5 font-medium"
                          style={{ color: "var(--foreground)" }}
                        >
                          <span
                            className="inline-block h-1.5 w-1.5 rounded-full"
                            style={{ background: EVENT_COLOR[e.event_type] ?? "var(--text-subtle)" }}
                            aria-hidden
                          />
                          {e.event_type}
                        </span>
                      </td>
                      <td className="px-3 py-2 font-mono" style={{ color: "var(--text-muted)" }}>
                        {e.llm_provider ?? "—"}
                      </td>
                      <td className="px-3 py-2 font-mono truncate max-w-[180px]" style={{ color: "var(--text-muted)" }} title={e.llm_model ?? ""}>
                        {e.llm_model ?? "—"}
                      </td>
                      <td className="px-3 py-2 text-right font-mono" style={{ color: "var(--text-muted)" }}>
                        {fmtTokens(e.token_input, e.token_output)}
                      </td>
                      <td className="px-3 py-2 text-right font-mono" style={{ color: "var(--text-muted)" }}>
                        {fmtCost(e.cost_usd)}
                      </td>
                      <td className="px-3 py-2 text-right font-mono" style={{ color: "var(--text-muted)" }}>
                        {fmtLatency(e.latency_ms)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div
      className="rounded-md border p-4"
      style={{ borderColor: "var(--border)", background: "var(--surface)" }}
    >
      <div className="flex items-center gap-2 mb-1">
        <Icon className="h-3.5 w-3.5" style={{ color: "var(--text-subtle)" }} aria-hidden />
        <span
          className="text-[10px] uppercase tracking-[0.14em] font-semibold"
          style={{ color: "var(--text-subtle)" }}
        >
          {label}
        </span>
      </div>
      <div className="text-2xl font-semibold tabular-nums tracking-tight" style={{ color: "var(--foreground)" }}>
        {value}
      </div>
      {hint && (
        <div className="text-[10px] mt-0.5 font-mono" style={{ color: "var(--text-subtle)" }}>
          {hint}
        </div>
      )}
    </div>
  );
}

function SectionHeader({
  eyebrow,
  title,
  hint,
}: {
  eyebrow: string;
  title: string;
  hint?: string;
}) {
  return (
    <div className="flex items-end justify-between gap-3 flex-wrap">
      <div>
        <div
          className="text-[10px] uppercase tracking-[0.14em] font-semibold mb-1"
          style={{ color: "var(--accent)" }}
        >
          {eyebrow}
        </div>
        <h2 className="text-lg font-semibold tracking-tight" style={{ color: "var(--foreground)" }}>
          {title}
        </h2>
      </div>
      {hint && (
        <span className="text-xs" style={{ color: "var(--text-subtle)" }}>{hint}</span>
      )}
    </div>
  );
}
