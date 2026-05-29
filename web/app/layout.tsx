import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";
import { BrandMark } from "@/components/brand-mark";
import { NavLink } from "@/components/nav-link";
import { PageShell } from "@/components/page-shell";
import { SystemStatus } from "@/components/system-status";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Lastenheft — Sovereign Multimodal RAG",
  description:
    "Self-hosted, EU AI Act-compliant multimodal RAG over German industrial technical documentation. ColPali + LangGraph + Qwen3, on-prem.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body
        suppressHydrationWarning
        className="min-h-full flex flex-col"
        style={{ background: "var(--background)", color: "var(--foreground)" }}
      >
        {/* --------------- HEADER (fixed) --------------- */}
        <header
          className="fixed top-0 left-0 right-0 z-50 border-b backdrop-blur-xl"
          style={{
            background: "color-mix(in srgb, var(--background) 80%, transparent)",
            borderColor: "var(--border)",
          }}
        >
          <div className="mx-auto max-w-[1400px] px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
            <Link href="/" className="flex items-center gap-3 group">
              <BrandMark size={28} />
              <div className="flex flex-col leading-tight">
                <span className="text-[15px] font-semibold tracking-tight">Lastenheft</span>
                <span
                  className="text-[10px] uppercase tracking-[0.14em] font-medium hidden sm:block"
                  style={{ color: "var(--text-subtle)" }}
                >
                  Sovereign Industrial RAG
                </span>
              </div>
            </Link>

            <div className="flex items-center gap-1 sm:gap-2">
              <SystemStatus />
              <nav className="flex items-center gap-0.5 ml-2">
                <NavLink href="/">Ask</NavLink>
                <NavLink href="/compliance">Compliance</NavLink>
                <a
                  href="https://github.com/Ekansh1605/Lastenheft"
                  target="_blank"
                  rel="noreferrer"
                  className="px-3 py-1.5 text-sm rounded-[3px] transition-colors flex items-center gap-1.5 hover:bg-[var(--surface-muted)]"
                  style={{ color: "var(--text-muted)" }}
                >
                  <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="currentColor" aria-hidden>
                    <path d="M12 .3a12 12 0 0 0-3.8 23.4c.6.1.8-.3.8-.6v-2.2c-3.3.7-4-1.6-4-1.6-.6-1.4-1.4-1.8-1.4-1.8-1.1-.8.1-.8.1-.8 1.2.1 1.9 1.3 1.9 1.3 1.1 1.9 2.9 1.4 3.6 1 .1-.8.4-1.4.8-1.7-2.7-.3-5.5-1.3-5.5-6 0-1.3.5-2.4 1.3-3.2-.1-.4-.6-1.6.1-3.2 0 0 1-.3 3.3 1.2a11.5 11.5 0 0 1 6 0c2.3-1.5 3.3-1.2 3.3-1.2.7 1.6.2 2.9.1 3.2.8.8 1.3 1.9 1.3 3.2 0 4.6-2.8 5.6-5.5 5.9.4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A12 12 0 0 0 12 .3" />
                  </svg>
                  <span className="hidden sm:inline">GitHub</span>
                </a>
              </nav>
            </div>
          </div>
        </header>

        {/* Spacer for fixed header height */}
        <div className="h-16 flex-shrink-0" aria-hidden />

        {/* PageShell adds md:pl-72 on routes that render a sidebar (currently
            only '/'), so the footer and main never disappear under it. */}
        <PageShell>
          <main className="flex-1">{children}</main>

          {/* --------------- FOOTER --------------- */}
          <footer
            className="border-t mt-12"
            style={{ background: "var(--surface)", borderColor: "var(--border)" }}
          >
          <div className="mx-auto max-w-6xl px-4 sm:px-6 py-8 grid grid-cols-1 sm:grid-cols-3 gap-6 text-xs">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <BrandMark size={20} />
                <span className="font-semibold tracking-tight" style={{ color: "var(--foreground)" }}>
                  Lastenheft
                </span>
              </div>
              <p style={{ color: "var(--text-muted)" }}>
                Built for German industrial Mittelstand.
                <br />
                Geschäftsgeheimnis stays on-prem.
              </p>
            </div>
            <div className="space-y-2">
              <div
                className="font-semibold uppercase tracking-[0.1em] text-[10px]"
                style={{ color: "var(--text-subtle)" }}
              >
                Stack
              </div>
              <div className="flex flex-wrap gap-1.5">
                {[
                  "ColPali", "LangGraph", "Qwen3 4B", "BGE+LoRA",
                  "FastAPI", "Next.js 16", "pgvector", "Langfuse",
                ].map((s) => (
                  <span
                    key={s}
                    className="px-1.5 py-0.5 rounded-[2px] font-mono text-[10px]"
                    style={{ background: "var(--surface-muted)", color: "var(--text-muted)" }}
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <div
                className="font-semibold uppercase tracking-[0.1em] text-[10px]"
                style={{ color: "var(--text-subtle)" }}
              >
                Compliance
              </div>
              <ul className="space-y-1" style={{ color: "var(--text-muted)" }}>
                <li>EU AI Act Art. 6 / 13 / 14</li>
                <li>GDPR Art. 17 right-to-erasure</li>
                <li>Audit trail per agent node</li>
              </ul>
            </div>
          </div>
          <div className="border-t py-3" style={{ borderColor: "var(--border)" }}>
            <div
              className="mx-auto max-w-6xl px-4 sm:px-6 text-[10px] font-mono"
              style={{ color: "var(--text-subtle)" }}
            >
              MIT · 2026 Ekansh Sharma
            </div>
          </div>
        </footer>
        </PageShell>
      </body>
    </html>
  );
}
