import Link from "next/link";
import type { ReactNode } from "react";
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
  return (
    <html lang="en">
      <body className="app-shell">
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
        <main className="site-main">
          <div className="container">{children}</div>
        </main>
        <footer className="site-footer">
          <div className="container">
            <p>Built to help researchers explore theological corpora faster.</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
