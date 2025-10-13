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

import styles from "./AppShell.module.css";

function classNames(
  ...classes: Array<string | false | null | undefined>
): string {
  return classes.filter(Boolean).join(" ");
}

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
    <div className={styles.shell}>
      {/* Accessibility: Announce navigation status */}
      <div role="status" aria-live="polite" aria-atomic="true" className="visually-hidden">
        {navigationStatus}
      </div>
      <aside className={styles.nav}>
        <Link href="/" className={styles.brand}>
          <span className={styles.brandName}>Theoria</span>
          <span className={styles.brandTagline}>Research workspace</span>
        </Link>
        <button
          type="button"
          className={styles.navToggle}
          aria-expanded={!isMobileNav || isNavOpen}
          aria-controls="app-shell-v2-nav-content"
          onClick={() => setIsNavOpen((open) => !open)}
          ref={navToggleRef}
        >
          <span className={styles.navToggleIcon} aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
          <span>{isNavOpen || !isMobileNav ? "Hide navigation" : "Show navigation"}</span>
        </button>
        <div
          id="app-shell-v2-nav-content"
          className={styles.navContent}
          data-open={!isMobileNav || isNavOpen}
          aria-hidden={isMobileNav && !isNavOpen}
          ref={navContentRef}
        >
          <nav className={styles.navGroups} aria-label="Primary">
            {navSections.map((section) => (
              <div key={section.label} className={styles.navGroup}>
                <p className={styles.navLabel}>{section.label}</p>
                <ul className={styles.navList}>
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
                          className={classNames(
                            styles.navLink,
                            isActive && styles.navLinkActive,
                            isLoading && styles.navLinkLoading,
                          )}
                          aria-current={isActive ? "page" : undefined}
                          aria-disabled={isLoading}
                          onClick={(e) => handleLinkClick(item.href, e, item.label)}
                        >
                          {item.label}
                          {isLoading && (
                            <span className={styles.navSpinner} aria-hidden="true" />
                          )}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </nav>
          <div className={styles.mode}>{modeSwitcher}</div>
        </div>
      </aside>
      <div className={styles.workspace}>
        <div className={styles.commandBar} role="banner">
          <div className={styles.commandPlaceholder} aria-hidden="true">
            Command palette coming soon
          </div>
          <div
            className={styles.commandActions}
            aria-label="Quick actions"
            role="group"
          >
            <button
              type="button"
              className={classNames(
                styles.actionButton,
                isPending && clickedHref === "/upload" && styles.actionLoading,
              )}
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
                <span className={styles.actionSpinner} aria-hidden="true" />
              )}
              {isPending && clickedHref === "/upload" ? "Navigating…" : "Upload sources"}
            </button>
          </div>
        </div>
        <main className={styles.content} id="main-content">
          {children}
        </main>
        <footer className={styles.footer}>
          <div>{footerMeta}</div>
          {footerLinks.length > 0 ? (
            <div className={styles.footerLinks}>
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
