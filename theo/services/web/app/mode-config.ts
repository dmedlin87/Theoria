export type ResearchModeId = "balanced" | "investigative" | "devotional";

export type ResearchMode = {
  id: ResearchModeId;
  label: string;
  description: string;
  emphasis: string[];
  suppressions: string[];
};

export const RESEARCH_MODES: Record<ResearchModeId, ResearchMode> = {
  balanced: {
    id: "balanced",
    label: "Balanced",
    description: "Blend of critical and devotional perspectives",
    emphasis: [
      "Peer-reviewed commentaries",
      "Historical background",
      "Moderate theological diversity",
    ],
    suppressions: ["Highly speculative claims"],
  },
  investigative: {
    id: "investigative",
    label: "Investigative",
    description: "Prioritises tensions, variants, and critical questions",
    emphasis: [
      "Textual variants",
      "Contradiction analysis",
      "Source criticism",
    ],
    suppressions: ["Devotional meditations", "Homiletical summaries"],
  },
  devotional: {
    id: "devotional",
    label: "Devotional",
    description: "Highlights pastoral, practical, and reflective insights",
    emphasis: [
      "Pastoral applications",
      "Spiritual reflections",
      "Practical guidance",
    ],
    suppressions: ["Technical textual disputes"],
  },
};

export const DEFAULT_MODE_ID: ResearchModeId = "balanced";

export const MODE_COOKIE_KEY = "theo-mode";
export const MODE_STORAGE_KEY = "theo.mode.preference";

export function isResearchModeId(value: unknown): value is ResearchModeId {
  return typeof value === "string" && value in RESEARCH_MODES;
}

export function formatEmphasisSummary(mode: ResearchMode): string {
  const emphasis = mode.emphasis.length
    ? mode.emphasis.join(", ")
    : "no specific emphasis";
  const suppressions = mode.suppressions.length
    ? mode.suppressions.join(", ")
    : "nothing in particular";
  return `${mode.label} mode emphasises ${emphasis} while softening ${suppressions}.`;
}
