"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  type ReactNode,
  useState,
  useTransition,
  useEffect,
  useRef,
} from "react";

import CommandPalette from "./CommandPalette";
import OfflineIndicator from "./OfflineIndicator";

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
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [clickedHref, setClickedHref] = useState<string | null>(null);
  const [navigationStatus, setNavigationStatus] = useState<string>("");
  const [isMobileNav, setIsMobileNav] = useState(false);
  const [isNavOpen, setIsNavOpen] = useState(true);
  const navContentRef = useRef<HTMLDivElement | null>(null);
  const navToggleRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 1024px)");

    const updateMatches = () => {
      setIsMobileNav(mediaQuery.matches);
    };

    updateMatches();

    mediaQuery.addEventListener("change", updateMatches);

    return () => {
      mediaQuery.removeEventListener("change", updateMatches);
    };
  }, []);

  useEffect(() => {
    if (isMobileNav) {
      setIsNavOpen(false);
    } else {
      setIsNavOpen(true);
    }
  }, [isMobileNav]);

  useEffect(() => {
    if (!isMobileNav) return;

    if (isNavOpen) {
      const firstFocusable = navContentRef.current?.querySelector<HTMLElement>(
        "a, button, [tabindex]:not([tabindex='-1'])",
      );
      firstFocusable?.focus();
    } else {
      navToggleRef.current?.focus();
    }
  }, [isMobileNav, isNavOpen]);

  useEffect(() => {
    if (!isMobileNav || !isNavOpen) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setIsNavOpen(false);
      }
    };

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isMobileNav, isNavOpen]);

  const handleLinkClick = (href: string, e: React.MouseEvent<HTMLAnchorElement>, label: string) => {
    // Allow default Link behavior for cmd/ctrl clicks
    if (e.metaKey || e.ctrlKey) return;

    e.preventDefault();
    setClickedHref(href);
    setNavigationStatus(`Navigating to ${label}`);
    if (isMobileNav) {
      setIsNavOpen(false);
      navToggleRef.current?.focus();
    }
    startTransition(() => {
      router.push(href);
    });
  };

  // Clear navigation status when transition completes
  useEffect(() => {
    if (!isPending && clickedHref) {
      const timer = setTimeout(() => {
        setClickedHref(null);
        setNavigationStatus("");
      }, 300);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [isPending, clickedHref]);

  return (
    <div className="app-shell-v2">
      <CommandPalette />
      <OfflineIndicator />
      {/* Accessibility: Announce navigation status */}
      <div role="status" aria-live="polite" aria-atomic="true" className="visually-hidden">
        {navigationStatus}
      </div>
      <aside className="app-shell-v2__nav">
        <Link href="/" className="app-shell-v2__brand">
          <span className="app-shell-v2__brand-name">Theoria</span>
          <span className="app-shell-v2__brand-tagline">Research workspace</span>
        </Link>
        <button
          type="button"
          className="app-shell-v2__nav-toggle"
          aria-expanded={!isMobileNav || isNavOpen}
          aria-controls="app-shell-v2-nav-content"
          onClick={() => setIsNavOpen((open) => !open)}
          ref={navToggleRef}
        >
          <span className="app-shell-v2__nav-toggle-icon" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
          <span>{isNavOpen || !isMobileNav ? "Hide navigation" : "Show navigation"}</span>
        </button>
        <div
          id="app-shell-v2-nav-content"
          className="app-shell-v2__nav-content"
          data-open={!isMobileNav || isNavOpen}
          aria-hidden={isMobileNav && !isNavOpen}
          ref={navContentRef}
        >
          <nav className="app-shell-v2__nav-groups" aria-label="Primary">
            {navSections.map((section) => (
              <div key={section.label} className="app-shell-v2__nav-group">
                <p className="app-shell-v2__nav-label">{section.label}</p>
                <ul className="app-shell-v2__nav-list">
                  {section.items.map((item) => {
                    const isActive = item.match
                      ? pathname.startsWith(item.match)
                      : pathname === item.href;
                    const isLoading = clickedHref === item.href && isPending;
                    return (
                      <li key={item.href}>
                        <Link
                          href={item.href}
                          prefetch={true}
                          className={
                            isActive
                              ? "app-shell-v2__nav-link is-active"
                              : isLoading
                              ? "app-shell-v2__nav-link is-loading"
                              : "app-shell-v2__nav-link"
                          }
                          aria-current={isActive ? "page" : undefined}
                          aria-disabled={isLoading}
                          onClick={(e) => handleLinkClick(item.href, e, item.label)}
                        >
                          {item.label}
                          {isLoading && (
                            <span className="nav-loading-spinner" aria-hidden="true" />
                          )}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </nav>
          <div className="app-shell-v2__mode">{modeSwitcher}</div>
        </div>
      </aside>
      <div className="app-shell-v2__workspace">
        <div className="app-shell-v2__command-bar" role="banner">
          <div className="app-shell-v2__command-placeholder" aria-hidden="true">
            Command palette coming soon
          </div>
          <div
            className="app-shell-v2__command-actions"
            aria-label="Quick actions"
            role="group"
          >
            <button
              type="button"
              className={
                isPending && clickedHref === "/upload"
                  ? "app-shell-v2__action is-loading"
                  : "app-shell-v2__action"
              }
              onClick={() => {
                setClickedHref("/upload");
                setNavigationStatus("Navigating to Upload sources");
                startTransition(() => {
                  router.push("/upload");
                });
              }}
              disabled={isPending && clickedHref === "/upload"}
              aria-label={
                isPending && clickedHref === "/upload"
                  ? "Navigating to upload page"
                  : "Navigate to upload page"
              }
            >
              {isPending && clickedHref === "/upload" && (
                <span className="action-loading-spinner" aria-hidden="true" />
              )}
              {isPending && clickedHref === "/upload" ? "Navigating…" : "Upload sources"}
            </button>
          </div>
        </div>
        <main className="app-shell-v2__content" id="main-content">
          <div key={pathname} className="page-transition">
            {children}
          </div>
        </main>
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
                    rel="noopener noreferrer"
                    aria-label={`${link.label} (opens in new tab)`}
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
