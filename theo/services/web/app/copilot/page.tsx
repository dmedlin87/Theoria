"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import ModeChangeBanner from "../components/ModeChangeBanner";
import ErrorCallout from "../components/ErrorCallout";
import { formatEmphasisSummary } from "../mode-config";
import { useMode } from "../mode-context";
import { getCitationManagerEndpoint } from "../lib/api";
import { createTheoApiClient } from "../lib/api-client";
import {
  dispatchSuggestionAction,
  extractTraceId,
  suggestionFromError,
  type FailureContext,
  type FailureSuggestion,
} from "../lib/failure-suggestions";

import QuickStartPresets from "./components/QuickStartPresets";
import WorkflowFormFields from "./components/WorkflowFormFields";
import WorkflowResultPanel from "./components/WorkflowResultPanel";
import WorkflowSelector from "./components/WorkflowSelector";
import type {
  CopilotResult,
  FeatureFlags,
  QuickStartPreset,
  RAGCitation,
  WorkflowId,
} from "./components/types";
import {
  useCitationExporter,
  useCollaborationWorkflow,
  useComparativeWorkflow,
  useCurationWorkflow,
  useDevotionalWorkflow,
  useExportWorkflow,
  useMultimediaWorkflow,
  useSermonWorkflow,
  useVerseWorkflow,
  type CollaborationFormState,
  type ComparativeFormState,
  type CurationFormState,
  type DevotionalFormState,
  type ExportFormState,
  type MultimediaFormState,
  type SermonFormState,
  type VerseFormState,
} from "./components/workflow-hooks";
import { EXPORT_PRESETS } from "./components/export-presets";

const WORKFLOWS: { id: WorkflowId; label: string; description: string }[] = [
  { id: "verse", label: "Verse brief", description: "Ask a grounded question anchored to a verse." },
  { id: "sermon", label: "Sermon prep", description: "Generate outlines and key points for a topic." },
  { id: "comparative", label: "Comparative analysis", description: "Compare viewpoints linked to an OSIS reference." },
  { id: "multimedia", label: "Multimedia digest", description: "Summarise key takeaways from audio & video sources." },
  { id: "devotional", label: "Devotional guide", description: "Compose reflections and prayers for a passage." },
  { id: "collaboration", label: "Collaboration reconciliation", description: "Synthesize viewpoints from a research thread." },
  { id: "curation", label: "Corpus curation", description: "Review recently ingested documents and summaries." },
  { id: "export", label: "Export presets", description: "Produce ready-to-share sermon and transcript bundles." },
];

const QUICK_START_PRESETS: QuickStartPreset[] = [
  {
    id: "mark-reliability",
    title: "Reliability of the Gospel of Mark",
    description: "Investigate the longer ending from Mark 16:9–20 without memorising OSIS codes.",
    workflow: "verse",
    verse: {
      passage: "Mark 16:9–20",
      question: "What evidence supports the reliability of this passage?",
    },
  },
  {
    id: "beatitudes-themes",
    title: "Themes in the Beatitudes",
    description: "Surface the key themes from Matthew 5:1-12 in a grounded summary.",
    workflow: "verse",
    verse: {
      passage: "Matthew 5:1-12",
      question: "What themes emerge in the Beatitudes?",
    },
  },
  {
    id: "logos-overview",
    title: "Prologue of John",
    description: "Review how John 1:1-5 presents the Logos and its implications.",
    workflow: "verse",
    verse: {
      passage: "John 1:1-5",
      question: "How does this passage describe the Logos?",
    },
  },
];

function extractCitationsFromResult(result: CopilotResult | null): RAGCitation[] {
  if (!result) {
    return [];
  }
  switch (result.kind) {
    case "verse":
    case "sermon":
    case "comparative":
    case "multimedia":
    case "devotional":
    case "collaboration":
      return result.payload.answer?.citations ?? [];
    default:
      return [];
  }
}

async function sendToCitationManager(endpoint: string, payload: unknown): Promise<void> {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
}

function triggerDownload(body: string, filename: string): void {
  const blob = new Blob([body], { type: "application/vnd.citationstyles.csl+json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(link.href);
}

type WorkflowOverrides = {
  verse?: Partial<VerseFormState>;
  sermon?: Partial<SermonFormState>;
  comparative?: Partial<ComparativeFormState>;
  multimedia?: Partial<MultimediaFormState>;
  devotional?: Partial<DevotionalFormState>;
  collaboration?: Partial<CollaborationFormState>;
  curation?: Partial<CurationFormState>;
  exportPreset?: Partial<ExportFormState>;
};

export default function CopilotPage(): JSX.Element {
  const { mode } = useMode();
  const router = useRouter();
  const apiClient = useMemo(() => createTheoApiClient(), []);
  const citationManagerEndpoint = useMemo(() => getCitationManagerEndpoint(), []);
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [workflow, setWorkflow] = useState<WorkflowId>("verse");
  const [result, setResult] = useState<CopilotResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [errorState, setErrorState] = useState<{
    message: string;
    suggestion: FailureSuggestion | null;
    traceId: string | null;
  } | null>(null);
  const [citationExportStatus, setCitationExportStatus] = useState<string | null>(null);
  const [isSendingCitations, setIsSendingCitations] = useState(false);

  const clearError = useCallback(() => {
    setErrorState(null);
  }, []);

  const recordError = useCallback(
    (error: unknown, fallbackMessage: string, context: FailureContext) => {
      const suggestion = suggestionFromError(error, context);
      const message =
        error instanceof Error && error.message ? error.message : fallbackMessage;
      const traceId = extractTraceId(error);
      setErrorState({
        message,
        suggestion,
        traceId: traceId ?? null,
      });
    },
    [],
  );

  const verseWorkflow = useVerseWorkflow(apiClient);
  const sermonWorkflow = useSermonWorkflow(apiClient);
  const comparativeWorkflow = useComparativeWorkflow(apiClient);
  const multimediaWorkflow = useMultimediaWorkflow(apiClient);
  const devotionalWorkflow = useDevotionalWorkflow(apiClient);
  const collaborationWorkflow = useCollaborationWorkflow(apiClient);
  const curationWorkflow = useCurationWorkflow(apiClient);
  const exportWorkflow = useExportWorkflow(apiClient);
  const { exportCitations } = useCitationExporter(apiClient);

  const resolveFailureContext = useCallback(
    (
      selected: WorkflowId,
      overrides?: WorkflowOverrides & { workflow?: WorkflowId },
    ): FailureContext => {
      switch (selected) {
        case "verse": {
          const base = verseWorkflow.form;
          const extra = overrides?.verse ?? {};
          return {
            question:
              extra.question ?? base.question ?? extra.passage ?? base.passage ?? undefined,
            osis: extra.osis ?? base.osis ?? undefined,
          };
        }
        case "sermon": {
          const base = sermonWorkflow.form;
          const extra = overrides?.sermon ?? {};
          return {
            question: extra.topic ?? base.topic ?? undefined,
            osis: extra.osis ?? base.osis ?? undefined,
          };
        }
        case "comparative": {
          const base = comparativeWorkflow.form;
          const extra = overrides?.comparative ?? {};
          return {
            question: extra.participants ?? base.participants ?? undefined,
            osis: extra.osis ?? base.osis ?? undefined,
          };
        }
        case "multimedia": {
          const base = multimediaWorkflow.form;
          const extra = overrides?.multimedia ?? {};
          return {
            question: extra.collection ?? base.collection ?? undefined,
          };
        }
        case "devotional": {
          const base = devotionalWorkflow.form;
          const extra = overrides?.devotional ?? {};
          return {
            question: extra.focus ?? base.focus ?? undefined,
            osis: extra.osis ?? base.osis ?? undefined,
          };
        }
        case "collaboration": {
          const base = collaborationWorkflow.form;
          const extra = overrides?.collaboration ?? {};
          return {
            question: extra.thread ?? base.thread ?? undefined,
            osis: extra.osis ?? base.osis ?? undefined,
          };
        }
        case "curation": {
          const base = curationWorkflow.form;
          const extra = overrides?.curation ?? {};
          return {
            question: extra.since ?? base.since ?? undefined,
          };
        }
        case "export": {
          const base = exportWorkflow.form;
          const extra = overrides?.exportPreset ?? {};
          return {
            question: extra.topic ?? base.topic ?? undefined,
            osis: extra.osis ?? base.osis ?? undefined,
          };
        }
        default:
          return {};
      }
    },
    [
      verseWorkflow.form,
      sermonWorkflow.form,
      comparativeWorkflow.form,
      multimediaWorkflow.form,
      devotionalWorkflow.form,
      collaborationWorkflow.form,
      curationWorkflow.form,
      exportWorkflow.form,
    ],
  );

  const handleSuggestionAction = useCallback(
    (suggestion: FailureSuggestion) => {
      dispatchSuggestionAction(suggestion.action, {
        openSearchPanel: ({ query, osis }) => {
          const params = new URLSearchParams();
          if (query) {
            params.set("q", query);
          }
          if (osis) {
            params.set("osis", osis);
          }
          const queryString = params.toString();
          router.push(queryString ? `/search?${queryString}` : "/search");
        },
        openUploadPanel: () => {
          router.push("/upload");
        },
        focusInput: () => {
          const form = document.querySelector<HTMLFormElement>("form");
          const field = form?.querySelector<HTMLElement>("input, textarea");
          field?.focus();
        },
      });
    },
    [router],
  );

  const renderSuggestionAction = useCallback(
    (suggestion: FailureSuggestion) => {
      const defaultLabel =
        suggestion.action.label ??
        (suggestion.action.kind === "open-search"
          ? "Open search"
          : suggestion.action.kind === "open-upload"
          ? "Open upload"
          : "Edit prompt");
      return (
        <button
          type="button"
          className="button secondary"
          onClick={() => handleSuggestionAction(suggestion)}
        >
          {defaultLabel}
        </button>
      );
    },
    [handleSuggestionAction],
  );

  const errorCallout = errorState ? (
    <ErrorCallout
      message={errorState.message}
      traceId={errorState.traceId}
      actions={
        errorState.suggestion ? renderSuggestionAction(errorState.suggestion) : undefined
      }
    />
  ) : null;

  useEffect(() => {
    let active = true;
    const loadFeatures = async () => {
      try {
        const payload = await apiClient.fetchFeatures();
        if (active) {
          setEnabled(Boolean((payload as FeatureFlags).ai_copilot));
          clearError();
        }
      } catch (fetchError) {
        if (active) {
          setEnabled(false);
          recordError(fetchError, "Unable to load feature flags", {});
        }
      }
    };
    void loadFeatures();
    return () => {
      active = false;
    };
  }, [apiClient, clearError, recordError]);

  const runWorkflow = async (
    overrides?: WorkflowOverrides & { workflow?: WorkflowId },
  ): Promise<void> => {
    setIsRunning(true);
    clearError();
    setResult(null);
    setCitationExportStatus(null);

    const selectedWorkflow = overrides?.workflow ?? workflow;
    try {
      if (selectedWorkflow === "verse") {
        const payload = await verseWorkflow.run(mode.id, overrides?.verse);
        setResult({ kind: "verse", payload });
      } else if (selectedWorkflow === "sermon") {
        const payload = await sermonWorkflow.run(mode.id, overrides?.sermon);
        setResult({ kind: "sermon", payload });
      } else if (selectedWorkflow === "comparative") {
        const payload = await comparativeWorkflow.run(mode.id, overrides?.comparative);
        setResult({ kind: "comparative", payload });
      } else if (selectedWorkflow === "multimedia") {
        const payload = await multimediaWorkflow.run(mode.id, overrides?.multimedia);
        setResult({ kind: "multimedia", payload });
      } else if (selectedWorkflow === "devotional") {
        const payload = await devotionalWorkflow.run(mode.id, overrides?.devotional);
        setResult({ kind: "devotional", payload });
      } else if (selectedWorkflow === "collaboration") {
        const payload = await collaborationWorkflow.run(mode.id, overrides?.collaboration);
        setResult({ kind: "collaboration", payload });
      } else if (selectedWorkflow === "curation") {
        const payload = await curationWorkflow.run(mode.id, overrides?.curation);
        setResult({ kind: "curation", payload });
      } else if (selectedWorkflow === "export") {
        const payload = await exportWorkflow.run(mode.id, overrides?.exportPreset);
        setResult({ kind: "export", payload });
      } else {
        throw new Error("Unsupported workflow selection.");
      }
    } catch (submitError) {
      recordError(
        submitError,
        "Unable to run the workflow",
        resolveFailureContext(selectedWorkflow, overrides),
      );
    } finally {
      setIsRunning(false);
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await runWorkflow();
  };

  const handleCitationExport = async (citations: RAGCitation[]) => {
    if (!citations.length) {
      setCitationExportStatus("No citations available to export.");
      return;
    }
    setCitationExportStatus(null);
    clearError();
    setIsSendingCitations(true);
    try {
      const payload = await exportCitations(citations);
      const cslBody = JSON.stringify(payload.csl, null, 2);
      const filename = `${payload.manifest.export_id || "theo-citations"}.csl.json`;
      if (citationManagerEndpoint) {
        await sendToCitationManager(citationManagerEndpoint, payload.manager_payload);
        setCitationExportStatus("Sent citations to the configured manager endpoint.");
      } else {
        triggerDownload(cslBody, filename);
        setCitationExportStatus("Downloaded CSL bibliography for the selected citations.");
      }
    } catch (exportError) {
      setCitationExportStatus(null);
      recordError(exportError, "Unable to export citations", {});
    } finally {
      setIsSendingCitations(false);
    }
  };

  const handleQuickStart = async (preset: QuickStartPreset) => {
    if (isRunning) {
      return;
    }
    const citations = extractCitationsFromResult(result);
    if (citations.length) {
      await handleCitationExport(citations);
    } else {
      setCitationExportStatus(null);
    }

    if (preset.workflow === "verse" && preset.verse) {
      verseWorkflow.setForm({
        passage: preset.verse.passage ?? "",
        question: preset.verse.question ?? "",
        osis: preset.verse.osis ?? "",
        useAdvanced: Boolean(preset.verse.useAdvanced),
      });
    }

    setWorkflow(preset.workflow);
    const overrides: WorkflowOverrides & { workflow: WorkflowId } = {
      workflow: preset.workflow,
    };
    if (preset.verse) {
      overrides.verse = preset.verse;
    }
    await runWorkflow(overrides);
  };

  if (enabled === false) {
    return (
      <section>
        <h2>Copilot</h2>
        <p>The AI copilot is not enabled for this deployment.</p>
        {errorCallout}
      </section>
    );
  }

  if (enabled === null) {
    return (
      <section>
        <h2>Copilot</h2>
        <p>Loading feature flags…</p>
      </section>
    );
  }

  return (
    <section>
      <h2>Copilot</h2>
      <p>Run grounded workflows that stay anchored to your corpus.</p>
      <p style={{ marginTop: "0.5rem", color: "#4b5563" }}>{formatEmphasisSummary(mode)}</p>
      <ModeChangeBanner area="Copilot workspace" />

      <WorkflowSelector
        options={WORKFLOWS}
        selected={workflow}
        onSelect={(value) => setWorkflow(value as WorkflowId)}
      />

      <QuickStartPresets presets={QUICK_START_PRESETS} onSelect={handleQuickStart} disabled={isRunning} />

      <form onSubmit={handleSubmit} style={{ display: "grid", gap: "0.75rem", maxWidth: 600 }}>
        <WorkflowFormFields
          workflow={workflow}
          exportPresets={EXPORT_PRESETS}
          verse={{ form: verseWorkflow.form, onChange: verseWorkflow.setForm }}
          sermon={{ form: sermonWorkflow.form, onChange: sermonWorkflow.setForm }}
          comparative={{ form: comparativeWorkflow.form, onChange: comparativeWorkflow.setForm }}
          multimedia={{ form: multimediaWorkflow.form, onChange: multimediaWorkflow.setForm }}
          devotional={{ form: devotionalWorkflow.form, onChange: devotionalWorkflow.setForm }}
          collaboration={{ form: collaborationWorkflow.form, onChange: collaborationWorkflow.setForm }}
          curation={{ form: curationWorkflow.form, onChange: curationWorkflow.setForm }}
          exportPreset={{ form: exportWorkflow.form, onChange: exportWorkflow.setForm }}
        />

        <div className="workflow-status">
          {isRunning ? "Running workflow…" : "Ready."}
        </div>

        <button type="submit" className="button" disabled={isRunning}>
          {isRunning ? "Running." : "Run workflow"}
        </button>
      </form>

      <style jsx>{`
        .workflow-button {
          flex: 1 1 240px;
          min-width: 220px;
          text-align: left;
          border-radius: 0.75rem;
          padding: 0.75rem 1rem;
          border: 1px solid #cbd5f5;
          background: #fff;
          cursor: pointer;
          transition: border-color 0.2s ease, background 0.2s ease;
        }

        .workflow-button:disabled {
          cursor: not-allowed;
          opacity: 0.6;
        }

        .workflow-button:focus-visible {
          outline: 3px solid #1d4ed8;
        }

        .workflow-button.is-active {
          border: 2px solid #1d4ed8;
          background: #eff4ff;
        }

        .workflow-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 0.75rem;
        }

        .workflow-description {
          font-size: 0.85rem;
          color: #555;
        }

        .workflow-indicator {
          font-size: 0.8rem;
          font-weight: 600;
          color: #1d4ed8;
          display: inline-flex;
          align-items: center;
          gap: 0.25rem;
        }

        .workflow-indicator::before {
          content: "✓";
          font-size: 0.85rem;
        }

        .workflow-status {
          margin-bottom: 1rem;
        }

        .sr-only {
          border: 0;
          clip: rect(0 0 0 0);
          height: 1px;
          margin: -1px;
          overflow: hidden;
          padding: 0;
          position: absolute;
          width: 1px;
        }
      `}</style>

      {errorCallout && <div style={{ marginTop: "1rem" }}>{errorCallout}</div>}

      {result && (
        <WorkflowResultPanel
          result={result}
          onExport={handleCitationExport}
          exporting={isSendingCitations}
          status={citationExportStatus}
          summary={formatEmphasisSummary(mode)}
        />
      )}
    </section>
  );
}
