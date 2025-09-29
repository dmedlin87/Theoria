export type AdvancedToolId = "verse-research" | "verse-brief";

export type AdvancedToolDescriptor = {
  id: AdvancedToolId;
  label: string;
  description: string;
  kind: "panel" | "workflow";
  slashCommands?: string[];
  permissions?: {
    research?: boolean;
    aiCopilot?: boolean;
  };
};

export const ADVANCED_TOOLS: AdvancedToolDescriptor[] = [
  {
    id: "verse-research",
    label: "Verse research panels",
    description: "Open contradictions, textual variants, and notes for a verse alongside chat.",
    kind: "panel",
    slashCommands: ["/research", "/r"],
    permissions: { research: true },
  },
  {
    id: "verse-brief",
    label: "Run verse brief",
    description: "Trigger the verse workflow using the current copilot inputs.",
    kind: "workflow",
    slashCommands: ["/brief"],
    permissions: { aiCopilot: true },
  },
];
