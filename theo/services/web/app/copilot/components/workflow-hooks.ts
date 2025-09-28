import { useCallback, useMemo, useState } from "react";

import { TheoApiClient, createTheoApiClient } from "../../lib/api-client";
import type {
  CollaborationResponse,
  ComparativeResponse,
  CorpusCurationReport,
  DevotionalResponse,
  ExportPresetId,
  ExportPresetResult,
  MultimediaDigestResponse,
  RAGCitation,
  SermonResponse,
  VerseResponse,
} from "./types";

export type VerseFormState = {
  osis: string;
  passage: string;
  question: string;
  useAdvanced: boolean;
};

export type SermonFormState = {
  topic: string;
  osis: string;
};

export type ComparativeFormState = {
  osis: string;
  participants: string;
};

export type MultimediaFormState = {
  collection: string;
};

export type DevotionalFormState = {
  osis: string;
  focus: string;
};

export type CollaborationFormState = {
  thread: string;
  osis: string;
  viewpoints: string;
};

export type CurationFormState = {
  since: string;
};

export type ExportFormState = {
  preset: ExportPresetId;
  topic: string;
  osis: string;
  documentId: string;
};

function useApiClient(provided?: TheoApiClient): TheoApiClient {
  return useMemo(() => provided ?? createTheoApiClient(), [provided]);
}

type WorkflowHook<TForm, TResult, TOverrides = Partial<TForm>> = {
  form: TForm;
  setForm: (updates: Partial<TForm>) => void;
  reset: () => void;
  run: (model: string, overrides?: TOverrides) => Promise<TResult>;
};

function useFormState<TForm>(initialState: TForm): [TForm, (updates: Partial<TForm>) => void, () => void] {
  const [form, setFormState] = useState<TForm>(initialState);
  const setForm = useCallback((updates: Partial<TForm>) => {
    setFormState((current) => ({ ...current, ...updates }));
  }, []);
  const reset = useCallback(() => {
    setFormState(initialState);
  }, [initialState]);
  return [form, setForm, reset];
}

export function useVerseWorkflow(client?: TheoApiClient): WorkflowHook<
  VerseFormState,
  VerseResponse,
  Partial<VerseFormState>
> {
  const api = useApiClient(client);
  const [form, setForm, reset] = useFormState<VerseFormState>({
    osis: "",
    passage: "",
    question: "",
    useAdvanced: false,
  });

  const run = useCallback(
    async (model: string, overrides?: Partial<VerseFormState>): Promise<VerseResponse> => {
      const nextForm = { ...form, ...(overrides ?? {}) };
      const useAdvanced = Boolean(nextForm.useAdvanced);
      const osis = nextForm.osis.trim();
      const passage = nextForm.passage.trim();
      const question = nextForm.question.trim();

      if (useAdvanced) {
        if (!osis) {
          throw new Error("Provide an OSIS reference.");
        }
      } else if (!passage) {
        throw new Error("Provide a passage to analyse.");
      }

      return api.runVerseWorkflow({
        model,
        osis: osis || null,
        passage: useAdvanced ? null : passage || null,
        question: question || null,
      });
    },
    [api, form],
  );

  return { form, setForm, reset, run };
}

export function useSermonWorkflow(client?: TheoApiClient): WorkflowHook<
  SermonFormState,
  SermonResponse
> {
  const api = useApiClient(client);
  const [form, setForm, reset] = useFormState<SermonFormState>({
    topic: "",
    osis: "",
  });

  const run = useCallback(
    async (model: string, overrides?: Partial<SermonFormState>): Promise<SermonResponse> => {
      const nextForm = { ...form, ...(overrides ?? {}) };
      const topic = nextForm.topic.trim();
      if (!topic) {
        throw new Error("Provide a sermon topic.");
      }
      const osis = nextForm.osis.trim();
      return api.runSermonWorkflow({
        model,
        topic,
        osis: osis || null,
      });
    },
    [api, form],
  );

  return { form, setForm, reset, run };
}

export function useComparativeWorkflow(client?: TheoApiClient): WorkflowHook<
  ComparativeFormState,
  ComparativeResponse
> {
  const api = useApiClient(client);
  const [form, setForm, reset] = useFormState<ComparativeFormState>({
    osis: "",
    participants: "",
  });

  const run = useCallback(
    async (model: string, overrides?: Partial<ComparativeFormState>): Promise<ComparativeResponse> => {
      const nextForm = { ...form, ...(overrides ?? {}) };
      const osis = nextForm.osis.trim();
      if (!osis) {
        throw new Error("Provide an OSIS reference.");
      }
      const participants = nextForm.participants
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
      if (participants.length < 2) {
        throw new Error("Add at least two participants to compare.");
      }
      return api.runComparativeWorkflow({
        model,
        osis,
        participants,
      });
    },
    [api, form],
  );

  return { form, setForm, reset, run };
}

export function useMultimediaWorkflow(client?: TheoApiClient): WorkflowHook<
  MultimediaFormState,
  MultimediaDigestResponse
> {
  const api = useApiClient(client);
  const [form, setForm, reset] = useFormState<MultimediaFormState>({
    collection: "",
  });

  const run = useCallback(
    async (model: string, overrides?: Partial<MultimediaFormState>): Promise<MultimediaDigestResponse> => {
      const nextForm = { ...form, ...(overrides ?? {}) };
      const collection = nextForm.collection.trim();
      return api.runMultimediaWorkflow({
        model,
        collection: collection || null,
      });
    },
    [api, form],
  );

  return { form, setForm, reset, run };
}

export function useDevotionalWorkflow(client?: TheoApiClient): WorkflowHook<
  DevotionalFormState,
  DevotionalResponse
> {
  const api = useApiClient(client);
  const [form, setForm, reset] = useFormState<DevotionalFormState>({
    osis: "",
    focus: "",
  });

  const run = useCallback(
    async (model: string, overrides?: Partial<DevotionalFormState>): Promise<DevotionalResponse> => {
      const nextForm = { ...form, ...(overrides ?? {}) };
      const osis = nextForm.osis.trim();
      if (!osis) {
        throw new Error("Provide an OSIS reference.");
      }
      const focus = nextForm.focus.trim();
      if (!focus) {
        throw new Error("Provide a devotional focus.");
      }
      return api.runDevotionalWorkflow({
        model,
        osis,
        focus,
      });
    },
    [api, form],
  );

  return { form, setForm, reset, run };
}

export function useCollaborationWorkflow(client?: TheoApiClient): WorkflowHook<
  CollaborationFormState,
  CollaborationResponse
> {
  const api = useApiClient(client);
  const [form, setForm, reset] = useFormState<CollaborationFormState>({
    thread: "",
    osis: "",
    viewpoints: "",
  });

  const run = useCallback(
    async (model: string, overrides?: Partial<CollaborationFormState>): Promise<CollaborationResponse> => {
      const nextForm = { ...form, ...(overrides ?? {}) };
      const thread = nextForm.thread.trim();
      if (!thread) {
        throw new Error("Provide a thread identifier.");
      }
      const osis = nextForm.osis.trim();
      if (!osis) {
        throw new Error("Provide an OSIS reference.");
      }
      const viewpoints = nextForm.viewpoints
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
      if (viewpoints.length < 2) {
        throw new Error("Add at least two viewpoints to reconcile.");
      }
      return api.runCollaborationWorkflow({
        model,
        thread,
        osis,
        viewpoints,
      });
    },
    [api, form],
  );

  return { form, setForm, reset, run };
}

export function useCurationWorkflow(client?: TheoApiClient): WorkflowHook<
  CurationFormState,
  CorpusCurationReport
> {
  const api = useApiClient(client);
  const [form, setForm, reset] = useFormState<CurationFormState>({
    since: "",
  });

  const run = useCallback(
    async (model: string, overrides?: Partial<CurationFormState>): Promise<CorpusCurationReport> => {
      const nextForm = { ...form, ...(overrides ?? {}) };
      const since = nextForm.since.trim();
      if (since && Number.isNaN(Date.parse(since))) {
        throw new Error("Provide an ISO 8601 timestamp (YYYY-MM-DD or similar).");
      }
      return api.runCurationWorkflow({
        model,
        since: since || null,
      });
    },
    [api, form],
  );

  return { form, setForm, reset, run };
}

const SERMON_EXPORT_FORMATS: Record<Extract<ExportPresetId, `sermon-${string}`>, string> = {
  "sermon-markdown": "markdown",
  "sermon-ndjson": "ndjson",
  "sermon-csv": "csv",
};

const TRANSCRIPT_EXPORT_FORMATS: Record<Extract<ExportPresetId, `transcript-${string}`>, string> = {
  "transcript-markdown": "markdown",
  "transcript-csv": "csv",
};

export function useExportWorkflow(client?: TheoApiClient): WorkflowHook<
  ExportFormState,
  ExportPresetResult,
  Partial<ExportFormState>
> {
  const api = useApiClient(client);
  const [form, setForm, reset] = useFormState<ExportFormState>({
    preset: "sermon-markdown",
    topic: "",
    osis: "",
    documentId: "",
  });

  const run = useCallback(
    async (model: string, overrides?: Partial<ExportFormState>): Promise<ExportPresetResult> => {
      const nextForm = { ...form, ...(overrides ?? {}) };
      const preset = nextForm.preset;
      if (preset.startsWith("sermon")) {
        const topic = nextForm.topic.trim();
        if (!topic) {
          throw new Error("Provide a sermon topic to export.");
        }
        const osis = nextForm.osis.trim();
        const format = SERMON_EXPORT_FORMATS[preset as keyof typeof SERMON_EXPORT_FORMATS];
        if (!format) {
          throw new Error("Select an export preset.");
        }
        return api.runSermonExport({
          model,
          topic,
          osis: osis || null,
          format,
        });
      }
      const documentId = nextForm.documentId.trim();
      if (!documentId) {
        throw new Error("Provide a document identifier to export.");
      }
      const format = TRANSCRIPT_EXPORT_FORMATS[
        preset as keyof typeof TRANSCRIPT_EXPORT_FORMATS
      ];
      if (!format) {
        throw new Error("Select an export preset.");
      }
      return api.runTranscriptExport({
        documentId,
        format,
      });
    },
    [api, form],
  );

  return { form, setForm, reset, run };
}

export type ExportCitationsHook = {
  exportCitations: (
    citations: RAGCitation[],
  ) => Promise<import("./types").CitationExportResponse>;
};

export function useCitationExporter(client?: TheoApiClient): ExportCitationsHook {
  const api = useApiClient(client);
  const exportCitations = useCallback(
    async (citations: RAGCitation[]) => {
      if (!citations.length) {
        throw new Error("No citations available to export.");
      }
      const invalidCitation = citations.find(
        (citation) => !citation.passage_id || !citation.passage_id.trim(),
      );
      if (invalidCitation) {
        throw new Error(
          "Citations must include a passage identifier before exporting.",
        );
      }
      return api.exportCitations({ citations });
    },
    [api],
  );
  return { exportCitations };
}
