"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import ErrorCallout from "../components/ErrorCallout";
import ModeChangeBanner from "../components/ModeChangeBanner";
import UiModeToggle from "../components/UiModeToggle";
import { formatEmphasisSummary } from "../mode-config";
import { useMode } from "../mode-context";
import { getCitationManagerEndpoint } from "../lib/api";
import { createTheoApiClient, TheoApiError } from "../lib/api-client";
import { useUiModePreference } from "../lib/useUiModePreference";
import { emitTelemetry } from "../lib/telemetry";
import { serializeSearchParams, type SearchFilters } from "../search/searchParams";

import QuickStartPresets from "./components/QuickStartPresets";
import WorkflowFormFields from "./components/WorkflowFormFields";
import WorkflowResultPanel from "./components/WorkflowResultPanel";
import WorkflowSelector from "./components/WorkflowSelector";
import type {
  CopilotResult,
  FeatureFlags,
  GuardrailSuggestion,
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
  const router = useRouter();
  const { mode } = useMode();
  const apiClient = useMemo(() => createTheoApiClient(), []);
  const citationManagerEndpoint = useMemo(() => getCitationManagerEndpoint(), []);
  const [uiMode, setUiMode] = useUiModePreference();
  const isAdvancedUi = uiMode === "advanced";
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [workflow, setWorkflow] = useState<WorkflowId>("verse");
  const [result, setResult] = useState<CopilotResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<{ message: string; suggestions?: GuardrailSuggestion[] } | null>(null);
  const [citationExportStatus, setCitationExportStatus] = useState<string | null>(null);
  const [isSendingCitations, setIsSendingCitations] = useState(false);

  const verseWorkflow = useVerseWorkflow(apiClient);
  const sermonWorkflow = useSermonWorkflow(apiClient);
  const comparativeWorkflow = useComparativeWorkflow(apiClient);
  const multimediaWorkflow = useMultimediaWorkflow(apiClient);
  const devotionalWorkflow = useDevotionalWorkflow(apiClient);
  const collaborationWorkflow = useCollaborationWorkflow(apiClient);
  const curationWorkflow = useCurationWorkflow(apiClient);
  const exportWorkflow = useExportWorkflow(apiClient);
  const { exportCitations } = useCitationExporter(apiClient);

  useEffect(() => {
    let active = true;
    const loadFeatures = async () => {
      try {
        const payload = await apiClient.fetchFeatures();
        if (active) {
          setEnabled(Boolean((payload as FeatureFlags).ai_copilot));
        }
      } catch (fetchError) {
        if (active) {
          setEnabled(false);
          const message =
            fetchError instanceof Error && fetchError.message
              ? fetchError.message
              : "Unable to load feature flags";
          setError({ message });
        }
      }
    };
    void loadFeatures();
    return () => {
      active = false;
    };
  }, [apiClient]);

  useEffect(() => {
    if (!isAdvancedUi && workflow !== "verse") {
      setWorkflow("verse");
    }
  }, [isAdvancedUi, workflow]);

  const runWorkflow = async (
    overrides?: WorkflowOverrides & { workflow?: WorkflowId },
  ): Promise<void> => {
    setIsRunning(true);
    setError(null);
    setResult(null);
    setCitationExportStatus(null);

    const perf = typeof performance !== "undefined" ? performance : null;
    const requestStart = perf ? perf.now() : null;
    let retrievalEnd: number | null = null;
    let renderEnd: number | null = null;
    let telemetryWorkflow: WorkflowId | null = null;
    let telemetrySuccess = false;

    try {
      const selectedWorkflow = overrides?.workflow ?? workflow;
      telemetryWorkflow = selectedWorkflow;
      if (selectedWorkflow === "verse") {
        const payload = await verseWorkflow.run(mode.id, overrides?.verse);
        retrievalEnd = perf ? perf.now() : null;
        setResult({ kind: "verse", payload });
      } else if (selectedWorkflow === "sermon") {
        const payload = await sermonWorkflow.run(mode.id, overrides?.sermon);
        retrievalEnd = perf ? perf.now() : null;
        setResult({ kind: "sermon", payload });
      } else if (selectedWorkflow === "comparative") {
        const payload = await comparativeWorkflow.run(mode.id, overrides?.comparative);
        retrievalEnd = perf ? perf.now() : null;
        setResult({ kind: "comparative", payload });
      } else if (selectedWorkflow === "multimedia") {
        const payload = await multimediaWorkflow.run(mode.id, overrides?.multimedia);
        retrievalEnd = perf ? perf.now() : null;
        setResult({ kind: "multimedia", payload });
      } else if (selectedWorkflow === "devotional") {
        const payload = await devotionalWorkflow.run(mode.id, overrides?.devotional);
        retrievalEnd = perf ? perf.now() : null;
        setResult({ kind: "devotional", payload });
      } else if (selectedWorkflow === "collaboration") {
        const payload = await collaborationWorkflow.run(mode.id, overrides?.collaboration);
        retrievalEnd = perf ? perf.now() : null;
        setResult({ kind: "collaboration", payload });
      } else if (selectedWorkflow === "curation") {
        const payload = await curationWorkflow.run(mode.id, overrides?.curation);
        retrievalEnd = perf ? perf.now() : null;
        setResult({ kind: "curation", payload });
      } else if (selectedWorkflow === "export") {
        const payload = await exportWorkflow.run(mode.id, overrides?.exportPreset);
        retrievalEnd = perf ? perf.now() : null;
        setResult({ kind: "export", payload });
      } else {
        throw new Error("Unsupported workflow selection.");
      }
      telemetrySuccess = true;
      renderEnd = perf ? perf.now() : null;
    } catch (submitError) {
      if (retrievalEnd === null && perf) {
        retrievalEnd = perf.now();
      }
      renderEnd = perf ? perf.now() : null;
      if (submitError instanceof TheoApiError) {
        const payload = submitError.payload;
        let message = submitError.message || "Unable to run the workflow";
        let suggestions: GuardrailSuggestion[] | undefined;
        if (payload && typeof payload === "object") {
          const detail = (payload as Record<string, unknown>).detail;
          if (detail && typeof detail === "object") {
            const detailObject = detail as Record<string, unknown>;
            if (typeof detailObject.message === "string") {
              message = detailObject.message;
            }
            const candidate = detailObject.suggestions;
            if (Array.isArray(candidate)) {
              suggestions = candidate as GuardrailSuggestion[];
            }
          }
        }
        setError({ message, suggestions });
      } else {
        const fallbackMessage =
          submitError instanceof Error && submitError.message
            ? submitError.message
            : "Unable to run the workflow";
        setError({ message: fallbackMessage });
      }
    } finally {
      setIsRunning(false);
      if (requestStart !== null && telemetryWorkflow) {
        const events: {
          event: string;
          durationMs: number;
          workflow?: string;
          metadata?: Record<string, unknown>;
        }[] = [];
        if (retrievalEnd !== null) {
          events.push({
            event: "copilot.retrieval",
            durationMs: Math.max(0, retrievalEnd - requestStart),
            workflow: telemetryWorkflow,
            metadata: { success: telemetrySuccess },
          });
        }
        if (renderEnd !== null) {
          const generationStart = retrievalEnd ?? requestStart;
          events.push({
            event: "copilot.generation",
            durationMs: Math.max(0, renderEnd - generationStart),
            workflow: telemetryWorkflow,
            metadata: { success: telemetrySuccess },
          });
        }
        void emitTelemetry(events, { page: "copilot" });
      }
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
    setError(null);
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
      const message =
        exportError instanceof Error && exportError.message
          ? exportError.message
          : "Unable to export citations";
      setError({ message });
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

  const handleSuggestionAction = useCallback(
    (suggestion: GuardrailSuggestion) => {
      if (suggestion.action !== "search") {
        return;
      }
      const filters = suggestion.filters ?? {};
      const params: Partial<SearchFilters> = {
        query: suggestion.query ?? "",
        osis: suggestion.osis ?? "",
        collection: filters.collection ?? "",
        author: filters.author ?? "",
        sourceType: filters.source_type ?? "",
        theologicalTradition: filters.theological_tradition ?? "",
        topicDomain: filters.topic_domain ?? "",
      };
      const queryString = serializeSearchParams(params);
      setUiMode("advanced");
      router.push(`/search${queryString ? `?${queryString}` : ""}`);
    },
    [router, setUiMode],
  );

  const workflowControls = (
    <>
      <WorkflowSelector
        options={WORKFLOWS}
        selected={workflow}
        onSelect={(value) => setWorkflow(value as WorkflowId)}
      />

      <QuickStartPresets presets={QUICK_START_PRESETS} onSelect={handleQuickStart} disabled={isRunning} />
    </>
  );

  if (enabled === false) {
    return (
      <section>
        <h2>Copilot</h2>
        <p>The AI copilot is not enabled for this deployment.</p>
        {error && <p role="alert">{error.message}</p>}
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

      <div style={{ margin: "1.5rem 0" }}>
        <UiModeToggle mode={uiMode} onChange={setUiMode} />
      </div>

      {isAdvancedUi ? (
        workflowControls
      ) : (
        <details
          style={{
            border: "1px solid #cbd5f5",
            borderRadius: "0.75rem",
            padding: "0.75rem 1rem",
            background: "#f8fafc",
            marginBottom: "1.5rem",
          }}
        >
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>
            Advanced workflows & presets
          </summary>
          <p style={{ margin: "0.75rem 0", fontSize: "0.9rem", color: "#475569" }}>
            Open this panel when you need sermon prep, exports, or quick-start presets. Everything stays one click away.
          </p>
          <div style={{ display: "grid", gap: "1rem" }}>{workflowControls}</div>
        </details>
      )}

      {!isAdvancedUi && (
        <p style={{ marginBottom: "1rem", color: "#475569" }}>
          Simple mode focuses on verse briefs. Expand the advanced panel to switch workflows.
        </p>
      )}

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

      {error && (
        <div style={{ marginTop: "1rem" }}>
          <ErrorCallout
            message={error.message}
            actions={
              error.suggestions ? (
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                  {error.suggestions.map((suggestion, index) => (
                    <button
                      key={`${suggestion.action}-${index}`}
                      type="button"
                      onClick={() => handleSuggestionAction(suggestion)}
                      title={suggestion.description ?? undefined}
                    >
                      {suggestion.label}
                    </button>
                  ))}
                </div>
              ) : undefined
            }
          />
        </div>
      )}

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
