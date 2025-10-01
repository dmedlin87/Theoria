import type { ReactNode } from "react";

import { DEFAULT_MODE_ID } from "./mode-config";
import { ModeProvider, ModeSwitcher } from "./mode-context";
import "./theme.css";
import "./globals.css";
import Link from "next/link";
import { AppShell, type AppShellNavSection } from "./components/AppShell";

export const metadata = {
  title: "Theo Engine",
  description: "Research engine for theology",
};

type NavItem = { href: string; label: string; variant?: "primary" };

const NAV_LINKS: NavItem[] = [
  { href: "/chat", label: "Chat", variant: "primary" },
  { href: "/search", label: "Search" },
  { href: "/verse/John.1.1", label: "Verse explorer" },
  { href: "/copilot", label: "Copilot" },
  { href: "/upload", label: "Upload" },
];

const adminLinks: NavItem[] =
  process.env.NEXT_PUBLIC_ENABLE_ADMIN === "true"
    ? [{ href: "/admin/digests", label: "Admin" }]
    : [];

export default function RootLayout({ children }: { children: ReactNode }) {
  const initialMode = DEFAULT_MODE_ID;
  const enableUiV2 = process.env.NEXT_PUBLIC_ENABLE_UI_V2 === "true";
  const navSections: AppShellNavSection[] = [
    {
      label: "Workspace",
      items: [
        { href: "/chat", label: "Chat studio", match: "/chat" },
        { href: "/copilot", label: "Copilot" },
      ],
    },
    {
      label: "Library",
      items: [
        { href: "/search", label: "Search" },
        { href: "/verse/John.1.1", label: "Verse explorer", match: "/verse" },
      ],
    },
    {
      label: "Corpora",
      items: [{ href: "/upload", label: "Uploads", match: "/upload" }],
    },
  ];

  if (adminLinks.length > 0) {
    navSections.push({
      label: "Admin",
      items: adminLinks.map((item) => ({
        href: item.href,
        label: item.label,
        match: item.href,
      })),
    });
  }

  const footerMeta = `© ${new Date().getFullYear()} Theo Engine • UI v2 preview`;

  return (
    <html lang="en">
      <body className="app-shell">
        <ModeProvider initialMode={initialMode}>
          {enableUiV2 ? (
            <AppShell
              navSections={navSections}
              modeSwitcher={<ModeSwitcher />}
              footerMeta={footerMeta}
            >
              {children}
            </AppShell>
          ) : (
            <>
              <header className="site-header">
                <div className="container site-header__content">
                  <Link href="/" className="brand">
                    Theo Engine
                  </Link>
                  <nav className="site-nav" aria-label="Primary">
                    {[...NAV_LINKS, ...adminLinks].map((item) => (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={
                          item.variant === "primary" ? "nav-link nav-link--primary" : "nav-link"
                        }
                      >
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
            </>
          )}
        </ModeProvider>
      </body>
    </html>
  );
}
