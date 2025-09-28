import type { components } from "../../lib/generated/api";

export type FeatureFlags = {
  ai_copilot?: boolean;
};

export type RAGCitation = components["schemas"]["RAGCitation"];

export type RAGAnswer = components["schemas"]["RAGAnswer"];

export type VerseResponse = {
  osis: string;
  question?: string | null;
  answer: RAGAnswer;
  follow_ups: string[];
};

export type SermonResponse = {
  topic: string;
  osis?: string | null;
  outline: string[];
  key_points: string[];
  answer: RAGAnswer;
};

export type ComparativeResponse = {
  osis: string;
  participants: string[];
  comparisons: string[];
  answer: RAGAnswer;
};

export type MultimediaDigestResponse = {
  collection: string | null;
  highlights: string[];
  answer: RAGAnswer;
};

export type DevotionalResponse = {
  osis: string;
  focus: string;
  reflection: string;
  prayer: string;
  answer: RAGAnswer;
};

export type CollaborationResponse = {
  thread: string;
  synthesized_view: string;
  answer: RAGAnswer;
};

export type CorpusCurationReport = {
  since: string;
  documents_processed: number;
  summaries: string[];
};

export type ExportPresetId =
  | "sermon-markdown"
  | "sermon-ndjson"
  | "sermon-csv"
  | "transcript-markdown"
  | "transcript-csv";

export type ExportPreset = {
  id: ExportPresetId;
  label: string;
  description: string;
  type: "sermon" | "transcript";
  format: "markdown" | "ndjson" | "csv";
};

export type ExportPresetResult = {
  preset: ExportPresetId;
  label: string;
  format: string;
  filename: string | null;
  mediaType: string | null;
  content: string;
};

export type ExportManifest = components["schemas"]["ExportManifest"];

export type CitationExportResponse = components["schemas"]["CitationExportResponse"];

export type CopilotResult =
  | { kind: "verse"; payload: VerseResponse }
  | { kind: "sermon"; payload: SermonResponse }
  | { kind: "comparative"; payload: ComparativeResponse }
  | { kind: "multimedia"; payload: MultimediaDigestResponse }
  | { kind: "devotional"; payload: DevotionalResponse }
  | { kind: "collaboration"; payload: CollaborationResponse }
  | { kind: "curation"; payload: CorpusCurationReport }
  | { kind: "export"; payload: ExportPresetResult };

export type WorkflowId =
  | "verse"
  | "sermon"
  | "comparative"
  | "multimedia"
  | "devotional"
  | "collaboration"
  | "curation"
  | "export";

export type QuickStartPreset = {
  id: string;
  title: string;
  description: string;
  workflow: WorkflowId;
  verse?: {
    passage?: string;
    question?: string;
    osis?: string;
    useAdvanced?: boolean;
  };
};
