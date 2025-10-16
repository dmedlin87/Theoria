export type ResearchModeId = "detective" | "critic" | "apologist" | "synthesizer";

export type ResearchMode = {
  id: ResearchModeId;
  label: string;
  icon: string;
  tagline: string;
  description: string;
  emphasis: string[];
  suppressions: string[];
};

export const RESEARCH_MODES: Record<ResearchModeId, ResearchMode> = {
  detective: {
    id: "detective",
    label: "Detective",
    icon: "🔍",
    tagline: "Investigates step-by-step and documents every inference.",
    description:
      "Unpacks questions like a textual sleuth, mapping evidence chains and contradictions before forming conclusions.",
    emphasis: [
      "Step-by-step reasoning traces",
      "Contradiction mapping",
      "Source corroboration",
    ],
    suppressions: ["Uncited leaps", "Devotional speculation"],
  },
  critic: {
    id: "critic",
    label: "Critic",
    icon: "🤔",
    tagline: "Stress-tests claims by surfacing counterarguments and weak spots.",
    description:
      "Acts as a skeptical peer reviewer who challenges assumptions, highlights tensions, and foregrounds disputed evidence.",
    emphasis: [
      "Counterarguments and critical questions",
      "Textual variants and disputed readings",
      "Scholarly disagreements",
    ],
    suppressions: ["Unquestioned harmonisations", "Pastoral glosses that skip evidence"],
  },
  apologist: {
    id: "apologist",
    label: "Apologist",
    icon: "🛡️",
    tagline: "Builds coherent defences that harmonise tensions and reinforce trust.",
    description:
      "Functions like a theological apologist who integrates sources, harmonises tensions, and foregrounds pastoral assurance.",
    emphasis: [
      "Historical defences and doctrinal cohesion",
      "Pastoral encouragement and hope",
      "Integration of classical interpretations",
    ],
    suppressions: ["Overly skeptical framings", "Unresolved contradictions"],
  },
  synthesizer: {
    id: "synthesizer",
    label: "Synthesizer",
    icon: "📊",
    tagline: "Maps the landscape to show agreements, tensions, and next steps.",
    description:
      "Operates as a research synthesiser that surveys viewpoints, surfaces consensus and disagreement, and charts follow-up work.",
    emphasis: [
      "Comparative viewpoints across traditions",
      "Key agreements and tensions",
      "Suggested follow-up research paths",
    ],
    suppressions: ["Single-perspective bias", "Premature conclusions without sources"],
  },
};

export const DEFAULT_MODE_ID: ResearchModeId = "synthesizer";

export const MODE_COOKIE_KEY = "theo-mode";
export const MODE_STORAGE_KEY = "theo.mode.preference";

export function isResearchModeId(value: unknown): value is ResearchModeId {
  return typeof value === "string" && Object.hasOwn(RESEARCH_MODES, value);
}

export function formatEmphasisSummary(mode: ResearchMode): string {
  const emphasis = mode.emphasis.length
    ? mode.emphasis.join(", ")
    : "no specific emphasis";
  const suppressions = mode.suppressions.length
    ? mode.suppressions.join(", ")
    : "nothing in particular";
  return `${mode.label} reasoning spotlights ${emphasis} while softening ${suppressions}.`;
}
