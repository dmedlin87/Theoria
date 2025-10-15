"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  type ReactNode,
  type MouseEvent,
  useState,
  useTransition,
  useEffect,
  useRef,
} from "react";
import { FocusTrapRegion } from "./a11y/FocusTrapRegion";

import styles from "./AppShell.module.css";

function classNames(
  ...classes: Array<string | false | null | undefined>
): string {
  return classes.filter(Boolean).join(" ");
}

import CommandPalette from "./CommandPalette";
import ConnectionStatusIndicator from "./ConnectionStatusIndicator";
import { ThemeToggle } from "./ThemeToggle";
import { HelpMenu } from "./help/HelpMenu";

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
  const [navPanelOpen, setNavPanelOpen] = useState(true);
  const navContentRef = useRef<HTMLDivElement | null>(null);
  const navToggleRef = useRef<HTMLButtonElement | null>(null);
  const isNavOpen = !isMobileNav || navPanelOpen;

  useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 1024px)");

    const updateMatches = () => {
      const mobile = mediaQuery.matches;
      setIsMobileNav(mobile);
      setNavPanelOpen(mobile ? false : true);
    };

    updateMatches();

    mediaQuery.addEventListener("change", updateMatches);

    return () => {
      mediaQuery.removeEventListener("change", updateMatches);
    };
  }, []);

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
        setNavPanelOpen(false);
      }
    };

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isMobileNav, isNavOpen]);

  const handleLinkClick = (href: string, e: MouseEvent<HTMLAnchorElement>, label: string) => {
    // Allow default Link behavior for cmd/ctrl clicks
    if (e.metaKey || e.ctrlKey) return;

    e.preventDefault();
    setClickedHref(href);
    setNavigationStatus(`Navigating to ${label}`);
    if (isMobileNav) {
      setNavPanelOpen(false);
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
          onClick={() => {
            if (isMobileNav) {
              setNavPanelOpen((open) => !open);
            }
          }}
          ref={navToggleRef}
        >
          <span className={styles.navToggleIcon} aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
          <span>{isNavOpen || !isMobileNav ? "Hide navigation" : "Show navigation"}</span>
        </button>
        <FocusTrapRegion
          active={isMobileNav && isNavOpen}
          initialFocus={() =>
            navContentRef.current?.querySelector<HTMLElement>("a, button, [tabindex]:not([tabindex='-1'])") ??
            navToggleRef.current ??
            document.body
          }
          fallbackFocus={() => navToggleRef.current ?? document.body}
        >
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
        </FocusTrapRegion>
      </aside>
      <div className={styles.workspace}>
        <CommandPalette />
        <div className={styles.commandBar} role="banner">
          <button
            type="button"
            className={styles.commandTrigger}
            onClick={() => {
              window.dispatchEvent(new KeyboardEvent('keydown', {
                key: 'k',
                metaKey: true,
                ctrlKey: true,
                bubbles: true
              }));
            }}
            aria-label="Open command palette"
            title="Open command palette (⌘K or Ctrl+K)"
          >
            <span className={styles.commandTriggerIcon}>⌘</span>
            <span className={styles.commandTriggerText}>Quick actions...</span>
            <kbd className={styles.commandTriggerKbd}>⌘K</kbd>
          </button>
          <ConnectionStatusIndicator className={styles.statusIndicator} />
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
          <div className={styles.footerMeta}>
            <span>{footerMeta}</span>
            <div className={styles.footerControls}>
              <ThemeToggle />
              <HelpMenu />
            </div>
          </div>
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
