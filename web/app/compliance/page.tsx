import { fetchAuditLog, fetchRiskClassifications } from "@/lib/api";
import type { AuditEvent } from "@/lib/types";

const CATEGORY_STYLE: Record<string, string> = {
  minimal: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  limited: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  high: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  unacceptable: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

const EVENT_STYLE: Record<string, string> = {
  planner: "text-purple-600 dark:text-purple-400",
  retriever: "text-blue-600 dark:text-blue-400",
  validator: "text-amber-600 dark:text-amber-400",
  synthesizer: "text-emerald-600 dark:text-emerald-400",
};

function fmtCost(c: number | null): string {
  if (!c || c === 0) return "—";
  return `$${c.toFixed(4)}`;
}
function fmtLatency(ms: number | null): string {
  if (!ms) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}
function fmtTokens(tin: number | null, tout: number | null): string {
  if (!tin && !tout) return "—";
  return `${tin ?? 0}/${tout ?? 0}`;
}

// Disable static caching so the page reflects the live DB on each visit.
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

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-6 space-y-8">
      <section className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">EU AI Act compliance</h1>
        <p className="text-sm text-neutral-600 dark:text-neutral-400">
          Risk classification, transparency obligations, and audit log — designed in, not bolted on.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-neutral-600 dark:text-neutral-400 uppercase tracking-wide">
          Article 6 risk classification
        </h2>
        {unreachable ? (
          <div className="rounded border border-amber-300 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-800 px-3 py-3 text-sm text-amber-800 dark:text-amber-300">
            Backend at <code>http://127.0.0.1:8000</code> is not reachable.
            Start it with{" "}
            <code className="font-mono">uvicorn api.main:app --reload</code>.
          </div>
        ) : (
          <div className="space-y-3">
            {classifications.map((c) => (
              <div
                key={c.component}
                className="border border-neutral-200 dark:border-neutral-800 rounded-md bg-white dark:bg-neutral-900 p-4 space-y-2"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-semibold capitalize">{c.component.replace("-", " ")}</div>
                    <div className="text-xs text-neutral-500 mt-0.5">
                      {c.article_refs.join(" • ")}
                    </div>
                  </div>
                  <span
                    className={`text-xs uppercase tracking-wide font-semibold px-2 py-1 rounded ${
                      CATEGORY_STYLE[c.category] ?? ""
                    }`}
                  >
                    {c.category}
                  </span>
                </div>
                <p className="text-sm text-neutral-700 dark:text-neutral-300 leading-relaxed">
                  {c.rationale}
                </p>
                {c.mitigations.length > 0 && (
                  <div className="pt-2 border-t border-neutral-100 dark:border-neutral-800">
                    <div className="text-xs font-semibold text-neutral-500 mb-1">Mitigations</div>
                    <ul className="text-xs text-neutral-600 dark:text-neutral-400 space-y-0.5">
                      {c.mitigations.map((m, i) => (
                        <li key={i}>• {m}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-neutral-600 dark:text-neutral-400 uppercase tracking-wide">
          Article 13 transparency obligations
        </h2>
        <div className="border border-neutral-200 dark:border-neutral-800 rounded-md bg-white dark:bg-neutral-900 p-4">
          <ul className="text-sm text-neutral-700 dark:text-neutral-300 space-y-2">
            <li>• Every answer surfaces the LLM provider + model used (Ask page, top-right of answer card)</li>
            <li>• Source citations on every fact (bracketed numbers in the answer)</li>
            <li>• Routing decisions (local vs API) logged with timestamp + cost</li>
            <li>• Full audit trail persisted to <code className="font-mono text-xs">audit_events</code> (see below)</li>
          </ul>
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 className="text-sm font-semibold text-neutral-600 dark:text-neutral-400 uppercase tracking-wide">
            Audit log
          </h2>
          <span className="text-xs text-neutral-500">
            most recent {audit.events.length} of {audit.total} events
          </span>
        </div>
        {audit.events.length === 0 ? (
          <div className="border border-neutral-200 dark:border-neutral-800 rounded-md bg-white dark:bg-neutral-900 p-6 text-center text-sm text-neutral-500">
            No events yet. Run a query on the <span className="font-medium">Ask</span> page —
            each query writes one row per agent node to <code className="font-mono">audit_events</code>.
          </div>
        ) : (
          <div className="border border-neutral-200 dark:border-neutral-800 rounded-md bg-white dark:bg-neutral-900 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-neutral-50 dark:bg-neutral-950 text-neutral-600 dark:text-neutral-400">
                  <tr>
                    <th className="text-left font-medium px-3 py-2">Timestamp</th>
                    <th className="text-left font-medium px-3 py-2">Event</th>
                    <th className="text-left font-medium px-3 py-2">Provider</th>
                    <th className="text-left font-medium px-3 py-2">Model</th>
                    <th className="text-right font-medium px-3 py-2">Tokens (in/out)</th>
                    <th className="text-right font-medium px-3 py-2">Cost</th>
                    <th className="text-right font-medium px-3 py-2">Latency</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100 dark:divide-neutral-800">
                  {audit.events.map((e) => (
                    <tr key={e.id} className="hover:bg-neutral-50 dark:hover:bg-neutral-950/50">
                      <td className="px-3 py-2 font-mono text-neutral-500">
                        {new Date(e.created_at).toLocaleString()}
                      </td>
                      <td className={`px-3 py-2 font-medium ${EVENT_STYLE[e.event_type] ?? ""}`}>
                        {e.event_type}
                      </td>
                      <td className="px-3 py-2 font-mono">{e.llm_provider ?? "—"}</td>
                      <td className="px-3 py-2 font-mono">{e.llm_model ?? "—"}</td>
                      <td className="px-3 py-2 font-mono text-right">{fmtTokens(e.token_input, e.token_output)}</td>
                      <td className="px-3 py-2 font-mono text-right">{fmtCost(e.cost_usd)}</td>
                      <td className="px-3 py-2 font-mono text-right">{fmtLatency(e.latency_ms)}</td>
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
