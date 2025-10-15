export type HelpResource = {
  id: string;
  label: string;
  description: string;
  href?: string;
  external?: boolean;
  keywords?: string;
};

const DEFAULT_DOCS_BASE = "https://github.com/theoria-app/Theoria/blob/main";
const DEFAULT_API_DOCS_URL = "http://localhost:8000/docs";

function buildDocsUrl(relativePath: string): string {
  const base =
    process.env.NEXT_PUBLIC_DOCS_BASE_URL ||
    process.env.NEXT_PUBLIC_REPOSITORY_DOCS_BASE ||
    DEFAULT_DOCS_BASE;
  const normalizedBase = base.replace(/\/$/, "");
  const normalizedPath = relativePath.replace(/^\//, "");
  return `${normalizedBase}/${normalizedPath}`;
}

export const HELP_RESOURCES: HelpResource[] = [
  {
    id: "start-here",
    label: "Getting started guide",
    description: "Launch scripts, prerequisites, and setup checks",
    href: buildDocsUrl("START_HERE.md"),
    external: true,
    keywords: "start onboarding help docs",
  },
  {
    id: "readme",
    label: "Project README",
    description: "Repository overview, workflows, and scripts",
    href: buildDocsUrl("README.md"),
    external: true,
    keywords: "readme documentation overview",
  },
  {
    id: "api-docs",
    label: "API reference",
    description: "Interactive FastAPI docs for testing endpoints",
    href: process.env.NEXT_PUBLIC_API_DOCS_URL || DEFAULT_API_DOCS_URL,
    external: true,
    keywords: "api swagger openapi",
  },
  {
    id: "auth-troubleshooting",
    label: "Authentication troubleshooting",
    description: "Resolve missing credentials and startup failures",
    href: buildDocsUrl("README.md#api-authentication"),
    external: true,
    keywords: "auth authentication troubleshooting",
  },
];

export const KEYBOARD_SHORTCUTS_RESOURCE: HelpResource = {
  id: "keyboard-shortcuts",
  label: "Keyboard shortcuts",
  description: "Reference for power users",
  keywords: "keyboard shortcuts hotkeys",
};
