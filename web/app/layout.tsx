import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Lastenheft — Sovereign Multimodal RAG",
  description:
    "Self-hosted, EU AI Act-compliant multimodal RAG over German industrial technical documentation.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-neutral-50 text-neutral-900 dark:bg-neutral-950 dark:text-neutral-50">
        <header className="border-b border-neutral-200 dark:border-neutral-800 bg-white/80 dark:bg-neutral-900/80 backdrop-blur">
          <div className="mx-auto max-w-6xl px-4 sm:px-6 h-14 flex items-center justify-between">
            <Link href="/" className="font-semibold tracking-tight flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" aria-hidden />
              <span>Lastenheft</span>
              <span className="hidden sm:inline text-xs font-normal text-neutral-500">
                sovereign multimodal RAG
              </span>
            </Link>
            <nav className="flex items-center gap-1 text-sm">
              <Link
                href="/"
                className="px-3 py-1.5 rounded hover:bg-neutral-100 dark:hover:bg-neutral-800"
              >
                Ask
              </Link>
              <Link
                href="/compliance"
                className="px-3 py-1.5 rounded hover:bg-neutral-100 dark:hover:bg-neutral-800"
              >
                Compliance
              </Link>
              <a
                href="https://github.com/Ekansh1605/Lastenheft"
                target="_blank"
                rel="noreferrer"
                className="px-3 py-1.5 rounded hover:bg-neutral-100 dark:hover:bg-neutral-800"
              >
                GitHub
              </a>
            </nav>
          </div>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-neutral-200 dark:border-neutral-800 py-4 text-center text-xs text-neutral-500">
          Built for German industrial Mittelstand. Geschäftsgeheimnis stays on-prem.
        </footer>
      </body>
    </html>
  );
}
