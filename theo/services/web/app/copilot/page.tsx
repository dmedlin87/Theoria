"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import ModeChangeBanner from "../components/ModeChangeBanner";
import { ADVANCED_TOOLS, type AdvancedToolId } from "../chat/tools";
import ResearchPanels from "../research/ResearchPanels";
import { fetchResearchFeatures } from "../research/features";
import type { ResearchFeatureFlags } from "../research/types";
import { formatEmphasisSummary } from "../mode-config";
import { useMode } from "../mode-context";
import { getCitationManagerEndpoint } from "../lib/api";
import { createTheoApiClient } from "../lib/api-client";

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

type ActiveToolState = {
  id: AdvancedToolId;
  osis?: string | null;
};

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
  const apiClient = useMemo(() => createTheoApiClient(), []);
  const citationManagerEndpoint = useMemo(() => getCitationManagerEndpoint(), []);
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [workflow, setWorkflow] = useState<WorkflowId>("verse");
  const [result, setResult] = useState<CopilotResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [citationExportStatus, setCitationExportStatus] = useState<string | null>(null);
  const [isSendingCitations, setIsSendingCitations] = useState(false);
  const [researchFeatures, setResearchFeatures] = useState<ResearchFeatureFlags | null>(null);
  const [researchFeaturesError, setResearchFeaturesError] = useState<string | null>(null);
  const [activeTool, setActiveTool] = useState<ActiveToolState | null>(null);
  const [drawerOsis, setDrawerOsis] = useState<string>("");

  const verseWorkflow = useVerseWorkflow(apiClient);
  const sermonWorkflow = useSermonWorkflow(apiClient);
  const comparativeWorkflow = useComparativeWorkflow(apiClient);
  const multimediaWorkflow = useMultimediaWorkflow(apiClient);
  const devotionalWorkflow = useDevotionalWorkflow(apiClient);
  const collaborationWorkflow = useCollaborationWorkflow(apiClient);
  const curationWorkflow = useCurationWorkflow(apiClient);
  const exportWorkflow = useExportWorkflow(apiClient);
  const { exportCitations } = useCitationExporter(apiClient);
  const verseResearchTool = useMemo(
    () => ADVANCED_TOOLS.find((tool) => tool.id === "verse-research"),
    [],
  );
  const researchLoading = researchFeatures === null && !researchFeaturesError;
  const researchEnabled = Boolean(researchFeatures?.research);
  const currentFormOsis = verseWorkflow.form.useAdvanced
    ? (verseWorkflow.form.osis ?? "").trim()
    : "";

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
          setError((fetchError as Error).message || "Unable to load feature flags");
        }
      }
    };
    void loadFeatures();
    return () => {
      active = false;
    };
  }, [apiClient]);

  useEffect(() => {
    let active = true;
    const loadResearchFeatures = async () => {
      try {
        const flags = await fetchResearchFeatures();
        if (active) {
          setResearchFeatures(flags);
          setResearchFeaturesError(null);
        }
      } catch (fetchError) {
        console.error("Failed to load research features", fetchError);
        if (active) {
          setResearchFeatures({});
          setResearchFeaturesError(
            (fetchError as Error).message || "Unable to load research capabilities",
          );
        }
      }
    };

    void loadResearchFeatures();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (activeTool?.id !== "verse-research") {
      return;
    }
    const hintedOsis =
      (activeTool.osis && activeTool.osis.trim()) ||
      (verseWorkflow.form.useAdvanced ? verseWorkflow.form.osis.trim() : "");
    setDrawerOsis(hintedOsis);
  }, [activeTool, verseWorkflow.form.osis, verseWorkflow.form.useAdvanced]);

  const runWorkflow = async (
    overrides?: WorkflowOverrides & { workflow?: WorkflowId },
  ): Promise<void> => {
    setIsRunning(true);
    setError(null);
    setResult(null);
    setCitationExportStatus(null);

    try {
      const selectedWorkflow = overrides?.workflow ?? workflow;
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
      setError((submitError as Error).message || "Unable to run the workflow");
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
      setError((exportError as Error).message || "Unable to export citations");
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

  const openResearchPanels = (osisHint?: string | null) => {
    setActiveTool({ id: "verse-research", osis: osisHint ?? null });
  };

  const closeActiveTool = () => {
    setActiveTool(null);
    setDrawerOsis("");
  };

  const handleVerseCommand = (rawInput: string): boolean => {
    const trimmed = rawInput.trim();
    if (!trimmed.startsWith("/")) {
      return false;
    }
    const [command, ...rest] = trimmed.slice(1).split(/\s+/);
    const normalized = command.toLowerCase();
    if (normalized === "research" || normalized === "r") {
      const candidate =
        rest.join(" ").trim() ||
        (verseWorkflow.form.useAdvanced ? verseWorkflow.form.osis.trim() : "");
      openResearchPanels(candidate || null);
      if (candidate) {
        verseWorkflow.setForm({ osis: candidate, useAdvanced: true });
      }
      verseWorkflow.setForm({ question: "" });
      return true;
    }
    if (normalized === "brief") {
      setWorkflow("verse");
      void runWorkflow({ workflow: "verse" });
      return true;
    }
    return false;
  };

  if (enabled === false) {
    return (
      <section>
        <h2>Copilot</h2>
        <p>The AI copilot is not enabled for this deployment.</p>
        {error && <p role="alert">{error}</p>}
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

      <section
        aria-label="Advanced tools"
        style={{
          marginTop: "1.5rem",
          padding: "1.25rem",
          border: "1px solid #e2e8f0",
          borderRadius: "0.75rem",
          background: "#f8fafc",
          display: "grid",
          gap: "0.75rem",
        }}
      >
        <header style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", justifyContent: "space-between" }}>
          <div style={{ maxWidth: "48ch" }}>
            <h3 style={{ margin: 0 }}>Advanced tools</h3>
            <p style={{ margin: "0.25rem 0 0", color: "#475569", fontSize: "0.9rem" }}>
              Launch research modules inline or trigger them with slash commands like <code>/research</code> from the
              question box.
            </p>
          </div>
          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "flex-start" }}>
            <button
              type="button"
              className="workflow-button"
              style={{ minWidth: "220px" }}
              disabled={!researchEnabled || researchLoading}
              onClick={() => openResearchPanels(currentFormOsis || null)}
            >
              <span className="workflow-header">
                <span>{verseResearchTool?.label ?? "Verse research panels"}</span>
              </span>
              <span className="workflow-description">
                {researchLoading
                  ? "Loading research capabilities…"
                  : verseResearchTool?.description ?? "Inspect contradictions and variants inline."}
              </span>
            </button>
          </div>
        </header>
        {researchFeaturesError ? (
          <p role="alert" style={{ margin: 0, color: "#b91c1c" }}>
            Unable to load research capabilities. {researchFeaturesError}
          </p>
        ) : null}
        {researchEnabled ? (
          <p style={{ margin: 0, color: "#64748b", fontSize: "0.85rem" }}>
            Tip: try <code>/research {currentFormOsis || "John.1.1"}</code> in the question field to open these panels
            without leaving the workspace.
          </p>
        ) : null}
      </section>

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
          onVerseCommand={handleVerseCommand}
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

        .advanced-tool-drawer {
          margin-top: 2rem;
          border: 1px solid #e2e8f0;
          border-radius: 0.75rem;
          padding: 1.25rem;
          background: #fff;
          display: grid;
          gap: 1rem;
        }

        .drawer-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 1rem;
        }

        .drawer-content {
          display: grid;
          gap: 1rem;
        }

        .drawer-input {
          display: grid;
          gap: 0.5rem;
          font-weight: 600;
        }

        .drawer-input input {
          padding: 0.5rem 0.75rem;
          border-radius: 0.5rem;
          border: 1px solid #cbd5f5;
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

      {activeTool?.id === "verse-research" && (
        <aside className="advanced-tool-drawer" aria-label="Verse research panels drawer">
          <div className="drawer-header">
            <div>
              <h3 style={{ margin: 0 }}>Verse research panels</h3>
              <p style={{ margin: "0.25rem 0 0", color: "#475569" }}>
                Inspect contradictions, cross-references, morphology, and commentaries inline while you chat.
              </p>
            </div>
            <button
              type="button"
              onClick={closeActiveTool}
              style={{
                border: "none",
                background: "transparent",
                color: "#1d4ed8",
                cursor: "pointer",
                fontWeight: 600,
              }}
            >
              Close
            </button>
          </div>
          <div className="drawer-content">
            <label className="drawer-input">
              <span>OSIS reference</span>
              <input
                type="text"
                value={drawerOsis}
                onChange={(event) => setDrawerOsis(event.target.value)}
                placeholder="John.1.1-5"
              />
            </label>

            {researchFeaturesError ? (
              <p role="alert" style={{ margin: 0, color: "#b91c1c" }}>
                {researchFeaturesError}
              </p>
            ) : null}

            {researchLoading ? (
              <p>Loading research capabilities…</p>
            ) : !researchEnabled ? (
              <p>
                Research panels are disabled for this deployment. Visit the verse explorer for the full dashboard, or
                contact an admin to enable research features.
              </p>
            ) : drawerOsis.trim() ? (
              <ResearchPanels osis={drawerOsis.trim()} features={researchFeatures ?? {}} />
            ) : (
              <p>Enter an OSIS reference above to load the verse research stack.</p>
            )}
          </div>
        </aside>
      )}

      {error && (
        <p role="alert" style={{ color: "crimson", marginTop: "1rem" }}>
          {error}
        </p>
      )}

      {result && (
        <WorkflowResultPanel
          result={result}
          onExport={handleCitationExport}
          exporting={isSendingCitations}
          status={citationExportStatus}
          summary={formatEmphasisSummary(mode)}
          workflowId={workflow}
        />
      )}
    </section>
  );
}
