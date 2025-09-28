import type { ExportPreset, ExportPresetId } from "./types";

export const EXPORT_PRESETS: ExportPreset[] = [
  {
    id: "sermon-markdown",
    label: "Sermon prep (Markdown)",
    description: "Download a Markdown outline for sermon planning.",
    type: "sermon",
    format: "markdown",
  },
  {
    id: "sermon-ndjson",
    label: "Sermon prep (NDJSON)",
    description: "Structured NDJSON export of sermon citations.",
    type: "sermon",
    format: "ndjson",
  },
  {
    id: "sermon-csv",
    label: "Sermon prep (CSV)",
    description: "Spreadsheet-ready CSV export of sermon citations.",
    type: "sermon",
    format: "csv",
  },
  {
    id: "sermon-pdf",
    label: "Sermon prep (PDF)",
    description: "Polished PDF outline ready for sharing or printing.",
    type: "sermon",
    format: "pdf",
  },
  {
    id: "transcript-markdown",
    label: "Transcript (Markdown)",
    description: "Render a transcript with citations in Markdown.",
    type: "transcript",
    format: "markdown",
  },
  {
    id: "transcript-csv",
    label: "Transcript (CSV)",
    description: "Generate a CSV bundle of transcript references.",
    type: "transcript",
    format: "csv",
  },
  {
    id: "transcript-pdf",
    label: "Transcript (PDF)",
    description: "Printable transcript with inline citations.",
    type: "transcript",
    format: "pdf",
  },
];

export const EXPORT_PRESET_LOOKUP = Object.fromEntries(
  EXPORT_PRESETS.map((preset) => [preset.id, preset] as const),
) satisfies Record<ExportPresetId, ExportPreset>;
