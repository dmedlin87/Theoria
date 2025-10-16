import type { ReactNode } from "react";

import { DEFAULT_MODE_ID } from "./mode-config";
import { ModeProvider, ModeSwitcher } from "./mode-context";
import "../styles/tokens.css";
import "./theme.css";
import "../styles/utilities.css";
import "./globals.css";
import Link from "next/link";
import { AppShell, type AppShellNavSection } from "./components/AppShell";
import { ToastProvider } from "./components/Toast";
import { WelcomeModal } from "./components/WelcomeModal";
import { ApiConfigProvider } from "./lib/api-config";
import { OnboardingOverlay } from "./components/onboarding/OnboardingOverlay";

export const metadata = {
  title: "Theoria",
  description: "Research engine for theology",
  manifest: "/manifest.json",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#6366f1" },
    { media: "(prefers-color-scheme: dark)", color: "#4f46e5" }
  ],
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Theoria"
  },
  viewport: {
    width: "device-width",
    initialScale: 1,
    maximumScale: 5,
  }
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
  const enableUiV2 = true; // UI v2 enabled - modern AppShell with command palette and sidebar
  const navSections: AppShellNavSection[] = [
    {
      label: "Workspace",
      items: [
        { href: "/dashboard", label: "Dashboard", match: "/dashboard" },
        { href: "/chat", label: "Chat studio", match: "/chat" },
        { href: "/copilot", label: "Copilot" },
      ],
    },
    {
      label: "Library",
      items: [
        { href: "/discoveries", label: "Discoveries", match: "/discoveries" },
        { href: "/search", label: "Search" },
        { href: "/verse/John.1.1", label: "Verse explorer", match: "/verse" },
      ],
    },
    {
      label: "Corpora",
      items: [{ href: "/upload", label: "Uploads", match: "/upload" }],
    },
    {
      label: "System",
      items: [{ href: "/settings", label: "Settings", match: "/settings" }],
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

  const footerMeta = `© ${new Date().getFullYear()} Theoria • UI v2 preview`;

  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main-content">
          Skip to main content
        </a>
        <ApiConfigProvider>
          <ModeProvider initialMode={initialMode}>
            <ToastProvider>
              <WelcomeModal />
              {enableUiV2 ? (
                <AppShell
                  navSections={navSections}
                  modeSwitcher={<ModeSwitcher />}
                  footerMeta={footerMeta}
                >
                  <>
                    {children}
                    <OnboardingOverlay />
                  </>
                </AppShell>
              ) : (
                <>
                  <header className="site-header">
                    <div className="container site-header__content">
                      <Link href="/" className="brand">
                        Theoria
                      </Link>
                      <nav className="site-nav" aria-label="Primary">
                        {[...NAV_LINKS, ...adminLinks].map((item) => (
                          <Link
                            key={item.href}
                            href={item.href}
                            prefetch={true}
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
                  <main className="site-main" id="main-content">
                    <div className="container">{children}</div>
                  </main>
                  <footer className="site-footer">
                    <div className="container">
                      <p>Built to help researchers explore theological corpora faster.</p>
                    </div>
                  </footer>
                </>
              )}
            </ToastProvider>
          </ModeProvider>
        </ApiConfigProvider>
      </body>
    </html>
  );
}