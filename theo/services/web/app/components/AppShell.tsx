"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

export type AppShellNavItem = {
  href: string;
  label: string;
  /**
   * Optional path prefix used to mark the item as active for nested routes
   * (e.g., `/verse/[osis]`).
   */
  match?: string;
};

export type AppShellNavSection = {
  label: string;
  items: AppShellNavItem[];
};

export type AppShellFooterLink = {
  href: string;
  label: string;
  external?: boolean;
};

interface AppShellProps {
  navSections: AppShellNavSection[];
  children: ReactNode;
  modeSwitcher: ReactNode;
  footerLinks?: AppShellFooterLink[];
  footerMeta: string;
}

export function AppShell({
  navSections,
  children,
  modeSwitcher,
  footerLinks = [],
  footerMeta,
}: AppShellProps) {
  const pathname = usePathname() ?? "";

  return (
    <div className="app-shell-v2">
      <aside className="app-shell-v2__nav">
        <Link href="/" className="app-shell-v2__brand">
          <span className="app-shell-v2__brand-name">Theo Engine</span>
          <span className="app-shell-v2__brand-tagline">Research workspace</span>
        </Link>
        <nav className="app-shell-v2__nav-groups" aria-label="Primary">
          {navSections.map((section) => (
            <div key={section.label} className="app-shell-v2__nav-group">
              <p className="app-shell-v2__nav-label">{section.label}</p>
              <ul className="app-shell-v2__nav-list">
                {section.items.map((item) => {
                  const isActive = item.match
                    ? pathname.startsWith(item.match)
                    : pathname === item.href;
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        className={
                          isActive
                            ? "app-shell-v2__nav-link is-active"
                            : "app-shell-v2__nav-link"
                        }
                        aria-current={isActive ? "page" : undefined}
                      >
                        {item.label}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
        <div className="app-shell-v2__mode">{modeSwitcher}</div>
      </aside>
      <div className="app-shell-v2__workspace">
        <div className="app-shell-v2__command-bar" role="banner">
          <button
            type="button"
            className="app-shell-v2__command-search"
            aria-label="Open command palette (coming soon)"
            aria-disabled="true"
            disabled
          >
            <span>Search or jump to…</span>
            <span className="app-shell-v2__command-search-kbd" aria-hidden="true">
              ⌘K
            </span>
          </button>
          <div
            className="app-shell-v2__command-actions"
            aria-label="Quick actions"
            role="group"
          >
            <button type="button" className="app-shell-v2__action" disabled title="Coming soon">
              New research notebook
            </button>
            <button type="button" className="app-shell-v2__action" disabled title="Coming soon">
              Upload sources
            </button>
          </div>
        </div>
        <main className="app-shell-v2__content">{children}</main>
        <footer className="app-shell-v2__footer">
          <div>{footerMeta}</div>
          {footerLinks.length > 0 ? (
            <div className="app-shell-v2__footer-links">
              {footerLinks.map((link) =>
                link.external ? (
                  <a
                    key={link.href}
                    href={link.href}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {link.label}
                  </a>
                ) : (
                  <Link key={link.href} href={link.href}>
                    {link.label}
                  </Link>
                ),
              )}
            </div>
          ) : null}
        </footer>
      </div>
    </div>
  );
}
