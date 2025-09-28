export type FeatureFlags = {
  ai_copilot?: boolean;
};

export type RAGCitation = {
  index: number;
  osis: string;
  anchor: string;
  snippet: string;
  document_id: string;
  document_title?: string | null;
  passage_id?: string;
  source_url?: string | null;
};

export type RAGAnswer = {
  summary: string;
  citations: RAGCitation[];
};

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

export type ExportManifest = {
  export_id: string;
  schema_version: string;
  created_at: string;
  type: string;
  filters: Record<string, unknown>;
  totals: Record<string, number>;
  cursor?: string | null;
  next_cursor?: string | null;
  mode?: string | null;
};

export type CitationExportResponse = {
  manifest: ExportManifest;
  records: Array<Record<string, unknown>>;
  csl: Array<Record<string, unknown>>;
  manager_payload: Record<string, unknown>;
};

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
