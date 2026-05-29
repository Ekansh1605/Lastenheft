"use client";

import { usePathname } from "next/navigation";

/**
 * Wraps <main> + <footer> so they get left-padding to clear the fixed
 * 72-unit-wide sidebar — but only on routes that actually render a sidebar.
 *
 * The sidebar lives in app/page.tsx (only on the home page). Without this
 * wrapper, the global footer in layout.tsx would render edge-to-edge and
 * disappear underneath the fixed sidebar on desktop.
 */
const ROUTES_WITH_SIDEBAR = ["/"];

export function PageShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "/";
  const hasSidebar = ROUTES_WITH_SIDEBAR.includes(pathname);
  return (
    <div className={hasSidebar ? "md:pl-72 flex flex-col flex-1" : "flex flex-col flex-1"}>
      {children}
    </div>
  );
}
