"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  const path = usePathname();
  const active = path === href || (href !== "/" && path?.startsWith(href));
  return (
    <Link
      href={href}
      className="px-3 py-1.5 text-sm rounded-[3px] transition-colors relative"
      style={{
        color: active ? "var(--foreground)" : "var(--text-muted)",
        background: active ? "var(--surface-muted)" : "transparent",
      }}
    >
      {children}
      {active && (
        <span
          aria-hidden
          className="absolute -bottom-[17px] left-1/2 -translate-x-1/2 h-[2px] w-6"
          style={{ background: "var(--accent)" }}
        />
      )}
    </Link>
  );
}
