import Link from "next/link";
import { cookies } from "next/headers";
import type { ReactNode } from "react";

import {
  DEFAULT_MODE_ID,
  MODE_COOKIE_KEY,
  ResearchModeId,
  isResearchModeId,
} from "./mode-config";
import { ModeProvider, ModeSwitcher } from "./mode-context";
import "./globals.css";

export const metadata = {
  title: "Theo Engine",
  description: "Research engine for theology",
};

const NAV_LINKS = [
  { href: "/search", label: "Search" },
  { href: "/upload", label: "Upload" },
  { href: "/copilot", label: "Copilot" },
  { href: "/verse/John.1.1", label: "Verse explorer" },
];

const adminLinks =
  process.env.NEXT_PUBLIC_ENABLE_ADMIN === "true"
    ? [{ href: "/admin/digests", label: "Admin" }]
    : [];

export default function RootLayout({ children }: { children: ReactNode }) {
  const cookieStore = cookies();
  const initialModeCookie = cookieStore.get(MODE_COOKIE_KEY)?.value;
  const initialMode: ResearchModeId = isResearchModeId(initialModeCookie)
    ? initialModeCookie
    : DEFAULT_MODE_ID;

  return (
    <html lang="en">
      <body className="app-shell">
        <ModeProvider initialMode={initialMode}>
          <header className="site-header">
            <div className="container site-header__content">
              <Link href="/" className="brand">
                Theo Engine
              </Link>
              <nav className="site-nav" aria-label="Primary">
                {[...NAV_LINKS, ...adminLinks].map((item) => (
                  <Link key={item.href} href={item.href} className="nav-link">
                    {item.label}
                  </Link>
                ))}
              </nav>
            </div>
          </header>
          <section className="mode-banner" aria-label="Research mode selection">
            <div className="container">
              <ModeSwitcher />
            </div>
          </section>
          <main className="site-main">
            <div className="container">{children}</div>
          </main>
          <footer className="site-footer">
            <div className="container">
              <p>Built to help researchers explore theological corpora faster.</p>
            </div>
          </footer>
        </ModeProvider>
      </body>
    </html>
  );
}
