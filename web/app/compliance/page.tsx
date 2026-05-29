import { fetchRiskClassifications } from "@/lib/api";

const CATEGORY_STYLE: Record<string, string> = {
  minimal: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  limited: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  high: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  unacceptable: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

// Render statically on the server using the backend's seeded classification.
// Tries to fetch from the API; falls back to a static notice if backend isn't up.
export default async function CompliancePage() {
  let classifications: Awaited<ReturnType<typeof fetchRiskClassifications>> = [];
  let unreachable = false;
  try {
    classifications = await fetchRiskClassifications();
  } catch {
    unreachable = true;
  }

  return (
    <div className="mx-auto max-w-5xl px-4 sm:px-6 py-6 space-y-8">
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
            <li>• Coverage confidence + reasoning escalation flag exposed to user</li>
          </ul>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-neutral-600 dark:text-neutral-400 uppercase tracking-wide">
          Audit log
        </h2>
        <div className="border border-neutral-200 dark:border-neutral-800 rounded-md bg-white dark:bg-neutral-900 p-4 text-sm text-neutral-600 dark:text-neutral-400">
          Persisted to <code className="font-mono text-xs">audit_events</code> table.
          Full UI for filtering and CSV export ships in the next iteration.
        </div>
      </section>
    </div>
  );
}
