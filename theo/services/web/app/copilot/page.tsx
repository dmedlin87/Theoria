"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

import ModeChangeBanner from "../components/ModeChangeBanner";
import { formatEmphasisSummary } from "../mode-config";
import { useMode } from "../mode-context";
import { getApiBaseUrl, getCitationManagerEndpoint } from "../lib/api";

type FeatureFlags = {
  ai_copilot?: boolean;
};

type RAGCitation = {
  index: number;
  osis: string;
  anchor: string;
  snippet: string;
  document_id: string;
  document_title?: string | null;
  passage_id?: string;
  source_url: string;
};

type RAGAnswer = {
  summary: string;
  citations: RAGCitation[];
};

type VerseResponse = {
  osis: string;
  question?: string | null;
  answer: RAGAnswer;
  follow_ups: string[];
};

type SermonResponse = {
  topic: string;
  osis?: string | null;
  outline: string[];
  key_points: string[];
  answer: RAGAnswer;
};

type ComparativeResponse = {
  osis: string;
  participants: string[];
  comparisons: string[];
  answer: RAGAnswer;
};

type MultimediaDigestResponse = {
  collection: string | null;
  highlights: string[];
  answer: RAGAnswer;
};

type DevotionalResponse = {
  osis: string;
  focus: string;
  reflection: string;
  prayer: string;
  answer: RAGAnswer;
};

type CollaborationResponse = {
  thread: string;
  synthesized_view: string;
  answer: RAGAnswer;
};

type CorpusCurationReport = {
  since: string;
  documents_processed: number;
  summaries: string[];
};

type ExportPresetId =
  | "sermon-markdown"
  | "sermon-ndjson"
  | "sermon-csv"
  | "transcript-markdown"
  | "transcript-csv";

type ExportPreset = {
  id: ExportPresetId;
  label: string;
  description: string;
  type: "sermon" | "transcript";
  format: "markdown" | "ndjson" | "csv";
};

type ExportPresetResult = {
  preset: ExportPresetId;
  label: string;
  format: string;
  filename: string | null;
  mediaType: string | null;
  content: string;
};

type ExportManifest = {
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

type CitationExportResponse = {
  manifest: ExportManifest;
  records: Array<Record<string, unknown>>;
  csl: Array<Record<string, unknown>>;
  manager_payload: Record<string, unknown>;
};

type CopilotResult =
  | { kind: "verse"; payload: VerseResponse }
  | { kind: "sermon"; payload: SermonResponse }
  | { kind: "comparative"; payload: ComparativeResponse }
  | { kind: "multimedia"; payload: MultimediaDigestResponse }
  | { kind: "devotional"; payload: DevotionalResponse }
  | { kind: "collaboration"; payload: CollaborationResponse }
  | { kind: "curation"; payload: CorpusCurationReport }
  | { kind: "export"; payload: ExportPresetResult };

type WorkflowId =
  | "verse"
  | "sermon"
  | "comparative"
  | "multimedia"
  | "devotional"
  | "collaboration"
  | "curation"
  | "export";

const EXPORT_PRESETS: ExportPreset[] = [
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
];

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

type QuickStartPreset = {
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

function extractFilename(disposition: string | null): string | null {
  if (!disposition) {
    return null;
  }
  const match = disposition.match(/filename="?([^";]+)"?/i);
  return match ? match[1] : null;
}

function renderCitations(
  citations: RAGCitation[],
  options?: {
    onExport?: (citations: RAGCitation[]) => void;
    exporting?: boolean;
    status?: string | null;
  }
): JSX.Element | null {
  if (!citations.length) {
    return null;
  }
  const { onExport, exporting, status } = options ?? {};
  return (
    <div style={{ marginTop: "1rem" }}>
      <h4>Citations</h4>
      <ol style={{ paddingLeft: "1.25rem" }}>
        {citations.map((citation) => (
          <li key={citation.index} style={{ marginBottom: "0.5rem" }}>
            <Link
              href={citation.source_url}
              prefetch={false}
              style={{
                display: "block",
                padding: "0.75rem",
                border: "1px solid #e2e8f0",
                borderRadius: "0.5rem",
                background: "#f8fafc",
                textDecoration: "none",
                color: "inherit",
              }}
              title={`${citation.document_title ?? "Document"} — ${citation.snippet}`}
            >
              <span style={{ fontWeight: 600 }}>
                {citation.osis} ({citation.anchor})
              </span>
              {citation.document_title && (
                <span style={{ display: "block", marginTop: "0.25rem", fontSize: "0.9rem", color: "#475569" }}>
                  {citation.document_title}
                </span>
              )}
              <span
                style={{
                  display: "block",
                  marginTop: "0.35rem",
                  fontStyle: "italic",
                  color: "#0f172a",
                  lineHeight: 1.4,
                }}
              >
                “{citation.snippet}”
              </span>
            </Link>
          </li>
        ))}
      </ol>
      {onExport && (
        <div style={{ marginTop: "0.75rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <button
            type="button"
            onClick={() => onExport(citations)}
            disabled={Boolean(exporting)}
            style={{ alignSelf: "flex-start" }}
          >
            {exporting ? "Sending citations…" : "Send to Zotero/Mendeley"}
          </button>
          {status && (
            <p role="status" style={{ color: "#2563eb", margin: 0 }}>
              {status}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function renderRAGAnswer(
  answer: RAGAnswer,
  options?: {
    followUps?: string[];
    onExport?: (citations: RAGCitation[]) => void;
    exporting?: boolean;
    status?: string | null;
  }
): JSX.Element {
  const followUps = options?.followUps;
  return (
    <div style={{ marginTop: "1.5rem" }}>
      <h4>Answer</h4>
      <p>{answer.summary}</p>
      {renderCitations(answer.citations, {
        onExport: options?.onExport,
        exporting: options?.exporting,
        status: options?.status,
      })}
      {followUps && followUps.length > 0 && (
        <div style={{ marginTop: "1rem" }}>
          <h4>Follow-up questions</h4>
          <ul>
            {followUps.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function CopilotPage(): JSX.Element {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [workflow, setWorkflow] = useState<WorkflowId>("verse");
  const [verseForm, setVerseForm] = useState({ osis: "", passage: "", question: "" });
  const [verseAdvanced, setVerseAdvanced] = useState(false);
  const [sermonForm, setSermonForm] = useState({ topic: "", osis: "" });
  const [comparativeForm, setComparativeForm] = useState({ osis: "", participants: "" });
  const [multimediaForm, setMultimediaForm] = useState({ collection: "" });
  const [devotionalForm, setDevotionalForm] = useState({ osis: "", focus: "" });
  const [collaborationForm, setCollaborationForm] = useState({ thread: "", osis: "", viewpoints: "" });
  const [curationForm, setCurationForm] = useState({ since: "" });
  const [exportForm, setExportForm] = useState({
    preset: EXPORT_PRESETS[0].id,
    topic: "",
    osis: "",
    documentId: "",
  });
  const [result, setResult] = useState<CopilotResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [citationExportStatus, setCitationExportStatus] = useState<string | null>(null);
  const [isSendingCitations, setIsSendingCitations] = useState(false);

  const activeWorkflow = useMemo(
    () => WORKFLOWS.find((item) => item.id === workflow),
    [workflow]
  );

  const baseUrl = useMemo(() => getApiBaseUrl().replace(/\/$/, ""), []);
  const citationManagerEndpoint = useMemo(
    () => getCitationManagerEndpoint(),
    []
  );

  useEffect(() => {
    let isMounted = true;
    const fetchFeatures = async () => {
      try {
        const response = await fetch(`${baseUrl}/features/`, { cache: "no-store" });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = (await response.json()) as Record<string, boolean>;
        if (isMounted) {
          setEnabled(Boolean((payload as FeatureFlags).ai_copilot));
        }
      } catch (fetchError) {
        if (isMounted) {
          setEnabled(false);
          setError((fetchError as Error).message || "Unable to load feature flags");
        }
      }
    };
    fetchFeatures();
    return () => {
      isMounted = false;
    };
  }, [baseUrl]);

  const runWorkflow = async (
    options?: {
      workflow?: WorkflowId;
      verse?: {
        passage?: string;
        question?: string;
        osis?: string;
        useAdvanced?: boolean;
      };
    }
  ) => {
    setIsRunning(true);
    setError(null);
    setResult(null);
    setCitationExportStatus(null);

    try {
      let response: Response;
      const selectedWorkflow = options?.workflow ?? workflow;
      if (selectedWorkflow === "verse") {
        const useAdvanced = options?.verse?.useAdvanced ?? verseAdvanced;
        const osis = (options?.verse?.osis ?? verseForm.osis).trim();
        const passage = (options?.verse?.passage ?? verseForm.passage).trim();
        const question = (options?.verse?.question ?? verseForm.question).trim();
        if (useAdvanced) {
          if (!osis) {
            throw new Error("Provide an OSIS reference.");
          }
        } else if (!passage) {
          throw new Error("Provide a passage to analyse.");
        }
        const body: Record<string, unknown> = { question: question || null };
        if (osis) {
          body.osis = osis;
        }
        if (passage) {
          body.passage = passage;
        }
        response = await fetch(`${baseUrl}/ai/verse`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },

               body: JSON.stringify({
            osis: verseForm.osis.trim(),
            question: verseForm.question.trim() || null,
            mode: mode.id,
          }),

        });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = (await response.json()) as VerseResponse;
        setResult({ kind: "verse", payload });
      } else if (selectedWorkflow === "sermon") {
        if (!sermonForm.topic.trim()) {
          throw new Error("Provide a sermon topic.");
        }
        response = await fetch(`${baseUrl}/ai/sermon-prep`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            topic: sermonForm.topic.trim(),
            osis: sermonForm.osis.trim() || null,
            mode: mode.id,
          }),
        });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = (await response.json()) as SermonResponse;
        setResult({ kind: "sermon", payload });
      } else if (selectedWorkflow === "comparative") {
        if (!comparativeForm.osis.trim()) {
          throw new Error("Provide an OSIS reference.");
        }
        const participants = comparativeForm.participants
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean);
        if (participants.length < 2) {
          throw new Error("Add at least two participants to compare.");
        }
        response = await fetch(`${baseUrl}/ai/comparative`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ osis: comparativeForm.osis.trim(), participants, mode: mode.id }),
        });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = (await response.json()) as ComparativeResponse;
        setResult({ kind: "comparative", payload });
      } else if (selectedWorkflow === "multimedia") {
        const collection = multimediaForm.collection.trim();
        response = await fetch(`${baseUrl}/ai/multimedia`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ collection: collection || null, mode: mode.id }),
        });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = (await response.json()) as MultimediaDigestResponse;
        setResult({ kind: "multimedia", payload });
      } else if (selectedWorkflow === "devotional") {
        if (!devotionalForm.osis.trim()) {
          throw new Error("Provide an OSIS reference.");
        }
        if (!devotionalForm.focus.trim()) {
          throw new Error("Provide a devotional focus.");
        }
        response = await fetch(`${baseUrl}/ai/devotional`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            osis: devotionalForm.osis.trim(),
            focus: devotionalForm.focus.trim(),
            mode: mode.id,
          }),
        });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = (await response.json()) as DevotionalResponse;
        setResult({ kind: "devotional", payload });
      } else if (selectedWorkflow === "collaboration") {
        if (!collaborationForm.thread.trim()) {
          throw new Error("Provide a thread identifier.");
        }
        if (!collaborationForm.osis.trim()) {
          throw new Error("Provide an OSIS reference.");
        }
        const viewpoints = collaborationForm.viewpoints
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean);
        if (viewpoints.length < 2) {
          throw new Error("Add at least two viewpoints to reconcile.");
        }
        response = await fetch(`${baseUrl}/ai/collaboration`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            thread: collaborationForm.thread.trim(),
            osis: collaborationForm.osis.trim(),
            viewpoints,
            mode: mode.id,
          }),
        });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = (await response.json()) as CollaborationResponse;
        setResult({ kind: "collaboration", payload });
      } else if (selectedWorkflow === "curation") {
        const since = curationForm.since.trim();
        if (since && Number.isNaN(Date.parse(since))) {
          throw new Error("Provide an ISO 8601 timestamp (YYYY-MM-DD or similar).");
        }
        response = await fetch(`${baseUrl}/ai/curation`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ since: since || null, mode: mode.id }),
        });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = (await response.json()) as CorpusCurationReport;
        setResult({ kind: "curation", payload });
      } else if (selectedWorkflow === "export") {
        const preset = EXPORT_PRESETS.find((item) => item.id === exportForm.preset);
        if (!preset) {
          throw new Error("Select an export preset.");
        }
        let url = `${baseUrl}/ai/sermon-prep/export?format=${preset.format}`;
        let body: Record<string, unknown> = {};
        if (preset.type === "sermon") {
          if (!exportForm.topic.trim()) {
            throw new Error("Provide a sermon topic to export.");
          }
          body = {
            topic: exportForm.topic.trim(),
            osis: exportForm.osis.trim() || null,
            mode: mode.id,
          };
        } else {
          url = `${baseUrl}/ai/transcript/export`;
          if (!exportForm.documentId.trim()) {
            throw new Error("Provide a document identifier to export.");
          }
          body = {
            document_id: exportForm.documentId.trim(),
            format: preset.format,
            mode: mode.id,
          };
        }
        response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = (await response.json()) as ExportPresetResult;
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

  const handleQuickStart = async (preset: QuickStartPreset) => {
    if (isRunning) {
      return;
    }

    setCitationExportStatus(null);
    setError(null);
    setIsSendingCitations(true);
    try {
      const response = await fetch(`${baseUrl}/ai/citations/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ citations, mode: mode.id }),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const payload = (await response.json()) as CitationExportResponse;
      const cslBody = JSON.stringify(payload.csl, null, 2);
      const filename = `${payload.manifest.export_id || "theo-citations"}.csl.json`;
      if (citationManagerEndpoint) {
        const managerResponse = await fetch(citationManagerEndpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload.manager_payload),
        });
        if (!managerResponse.ok) {
          throw new Error(await managerResponse.text());
        }
        setCitationExportStatus(
          "Sent citations to the configured manager endpoint."
        );
      } else {
        const blob = new Blob([cslBody], {
          type: "application/vnd.citationstyles.csl+json",
        });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(link.href);
        setCitationExportStatus(
          "Downloaded CSL bibliography for the selected citations."
        );
      }
    } catch (exportError) {
      setCitationExportStatus(null);
      setError((exportError as Error).message || "Unable to export citations");
    } finally {
      setIsSendingCitations(false);
    }
    await runWorkflow({
      workflow: preset.workflow,
      verse: preset.verse,
    });
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

      <div style={{ display: "flex", gap: "0.75rem", margin: "1.5rem 0", flexWrap: "wrap" }}>
        {WORKFLOWS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setWorkflow(item.id)}
            className={`workflow-button${workflow === item.id ? " is-active" : ""}`}
            aria-pressed={workflow === item.id}
          >
            <span className="workflow-header">
              <strong>{item.label}</strong>
              {workflow === item.id && (
                <span aria-hidden="true" className="workflow-indicator">
                  Selected
                </span>
              )}
            </span>
            <span className="workflow-description">{item.description}</span>
            <span className="sr-only">
              {workflow === item.id
                ? `${item.label} workflow currently selected.`
                : `Activate the ${item.label} workflow.`}
            </span>
          </button>
        ))}
      </div>

      <section
        style={{
          marginBottom: "1.5rem",
          padding: "1rem",
          background: "#f8fafc",
          borderRadius: "0.75rem",
          border: "1px solid #e2e8f0",
        }}
      >
        <h3 style={{ marginTop: 0, marginBottom: "0.5rem" }}>Quick start</h3>
        <p style={{ marginTop: 0, color: "#475569" }}>
          Use a preset prompt to auto-fill the form and run the workflow instantly.
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem" }}>
          {QUICK_START_PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              onClick={() => void handleQuickStart(preset)}
              disabled={isRunning}
              style={{
                flex: "1 1 240px",
                minWidth: 220,
                textAlign: "left",
                borderRadius: "0.75rem",
                padding: "0.75rem 1rem",
                border: "1px solid #cbd5f5",
                background: "#fff",
                cursor: isRunning ? "not-allowed" : "pointer",
              }}
            >
              <strong style={{ display: "block", marginBottom: "0.25rem" }}>{preset.title}</strong>
              <span style={{ fontSize: "0.85rem", color: "#475569" }}>{preset.description}</span>
            </button>
          ))}
        </div>
      </section>


      <form onSubmit={handleSubmit} style={{ display: "grid", gap: "0.75rem", maxWidth: 600 }}>
        {workflow === "verse" && (
          <>
            <label>
              Passage
              <input
                type="text"
                value={verseForm.passage}
                onChange={(event) =>
                  setVerseForm((prev) => ({ ...prev, passage: event.target.value }))
                }
                placeholder="Mark 16:9–20"
                required={!verseAdvanced}
                style={{ width: "100%" }}
              />
            </label>
            {!verseAdvanced && (
              <p style={{ margin: "-0.5rem 0 0", fontSize: "0.85rem", color: "#475569" }}>
                Describe a passage naturally, such as “Mark 16:9–20” or “John 1:1-5”. We will resolve the
                exact reference for you.
              </p>
            )}
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <input
                type="checkbox"
                checked={verseAdvanced}
                onChange={(event) => setVerseAdvanced(event.target.checked)}
              />
              Advanced mode (use OSIS)
            </label>
            {verseAdvanced && (
              <>
                <label>
                  OSIS reference
                  <input
                    type="text"
                    value={verseForm.osis}
                    onChange={(event) =>
                      setVerseForm((prev) => ({ ...prev, osis: event.target.value }))
                    }
                    placeholder="Mark.16.9-Mark.16.20"
                    required={verseAdvanced}
                    style={{ width: "100%" }}
                  />
                </label>
                <p style={{ margin: "-0.5rem 0 0", fontSize: "0.85rem", color: "#475569" }}>
                  OSIS uses Book.Chapter.Verse notation. Provide precise ranges like “Mark.16.9-Mark.16.20” when
                  you need exact control.
                </p>
              </>
            )}
            <label>
              Question
              <textarea
                value={verseForm.question}
                onChange={(event) => setVerseForm((prev) => ({ ...prev, question: event.target.value }))}
                rows={3}
                placeholder="What themes emerge in this passage?"
                style={{ width: "100%" }}
              />
            </label>
          </>
        )}

        {workflow === "sermon" && (
          <>
            <label>
              Sermon topic
              <input
                type="text"
                value={sermonForm.topic}
                onChange={(event) => setSermonForm((prev) => ({ ...prev, topic: event.target.value }))}
                placeholder="Grace and forgiveness"
                required
                style={{ width: "100%" }}
              />
            </label>
            <label>
              OSIS anchor (optional)
              <input
                type="text"
                value={sermonForm.osis}
                onChange={(event) => setSermonForm((prev) => ({ ...prev, osis: event.target.value }))}
                placeholder="Luke.15"
                style={{ width: "100%" }}
              />
            </label>
          </>
        )}

        {workflow === "comparative" && (
          <>
            <label>
              OSIS reference
              <input
                type="text"
                value={comparativeForm.osis}
                onChange={(event) =>
                  setComparativeForm((prev) => ({ ...prev, osis: event.target.value }))
                }
                placeholder="John.1.1"
                required
                style={{ width: "100%" }}
              />
            </label>
            <label>
              Participants (comma separated)
              <input
                type="text"
                value={comparativeForm.participants}
                onChange={(event) =>
                  setComparativeForm((prev) => ({ ...prev, participants: event.target.value }))
                }
                placeholder="Augustine, Luther, Calvin"
                required
                style={{ width: "100%" }}
              />
            </label>
          </>
        )}

        {workflow === "multimedia" && (
          <label>
            Collection (optional)
            <input
              type="text"
              value={multimediaForm.collection}
              onChange={(event) =>
                setMultimediaForm((prev) => ({ ...prev, collection: event.target.value }))
              }
              placeholder="Gospels"
              style={{ width: "100%" }}
            />
          </label>
        )}

        {workflow === "devotional" && (
          <>
            <label>
              OSIS reference
              <input
                type="text"
                value={devotionalForm.osis}
                onChange={(event) =>
                  setDevotionalForm((prev) => ({ ...prev, osis: event.target.value }))
                }
                placeholder="John.1.1-5"
                required
                style={{ width: "100%" }}
              />
            </label>
            <label>
              Focus theme
              <input
                type="text"
                value={devotionalForm.focus}
                onChange={(event) =>
                  setDevotionalForm((prev) => ({ ...prev, focus: event.target.value }))
                }
                placeholder="God's Word in creation"
                required
                style={{ width: "100%" }}
              />
            </label>
          </>
        )}

        {workflow === "collaboration" && (
          <>
            <label>
              Thread identifier
              <input
                type="text"
                value={collaborationForm.thread}
                onChange={(event) =>
                  setCollaborationForm((prev) => ({ ...prev, thread: event.target.value }))
                }
                placeholder="forum-thread-42"
                required
                style={{ width: "100%" }}
              />
            </label>
            <label>
              OSIS reference
              <input
                type="text"
                value={collaborationForm.osis}
                onChange={(event) =>
                  setCollaborationForm((prev) => ({ ...prev, osis: event.target.value }))
                }
                placeholder="Romans.8.1-4"
                required
                style={{ width: "100%" }}
              />
            </label>
            <label>
              Viewpoints (comma separated)
              <input
                type="text"
                value={collaborationForm.viewpoints}
                onChange={(event) =>
                  setCollaborationForm((prev) => ({ ...prev, viewpoints: event.target.value }))
                }
                placeholder="Logos Christology, Early Fathers, Reformers"
                required
                style={{ width: "100%" }}
              />
            </label>
          </>
        )}

        {workflow === "curation" && (
          <label>
            Since (ISO timestamp, optional)
            <input
              type="text"
              value={curationForm.since}
              onChange={(event) =>
                setCurationForm((prev) => ({ ...prev, since: event.target.value }))
              }
              placeholder="2024-01-01T00:00:00"
              style={{ width: "100%" }}
            />
          </label>
        )}

        {workflow === "export" && (
          <>
            <label>
              Export preset
              <select
                value={exportForm.preset}
                onChange={(event) =>
                  setExportForm((prev) => ({ ...prev, preset: event.target.value as ExportPresetId }))
                }
                name="exportPreset"
                style={{ width: "100%" }}
              >
                {EXPORT_PRESETS.map((preset) => (
                  <option key={preset.id} value={preset.id}>
                    {preset.label}
                  </option>
                ))}
              </select>
            </label>
            {(() => {
              const preset = EXPORT_PRESETS.find((item) => item.id === exportForm.preset);
              if (!preset) {
                return null;
              }
              if (preset.type === "sermon") {
                return (
                  <>
                    <p style={{ margin: 0, color: "#555" }}>{preset.description}</p>
                    <label>
                      Sermon topic
                      <input
                        type="text"
                        value={exportForm.topic}
                        onChange={(event) =>
                          setExportForm((prev) => ({ ...prev, topic: event.target.value }))
                        }
                        placeholder="Embodied hope"
                        required
                        style={{ width: "100%" }}
                      />
                    </label>
                    <label>
                      OSIS anchor (optional)
                      <input
                        type="text"
                        value={exportForm.osis}
                        onChange={(event) =>
                          setExportForm((prev) => ({ ...prev, osis: event.target.value }))
                        }
                        placeholder="John.1.1"
                        style={{ width: "100%" }}
                      />
                    </label>
                  </>
                );
              }
              return (
                <>
                  <p style={{ margin: 0, color: "#555" }}>{preset.description}</p>
                  <label>
                    Document identifier
                    <input
                      type="text"
                      value={exportForm.documentId}
                      onChange={(event) =>
                        setExportForm((prev) => ({ ...prev, documentId: event.target.value }))
                      }
                      placeholder="doc-123"
                      required
                      style={{ width: "100%" }}
                    />
                  </label>
                </>
              );
            })()}
          </>
        )}

        {workflow === "comparative" && (
          <>
            <label>
              OSIS reference
              <input
                type="text"
                value={comparativeForm.osis}
                onChange={(event) => setComparativeForm((prev) => ({ ...prev, osis: event.target.value }))}
                placeholder="Romans.5.1-5"
                required
                style={{ width: "100%" }}
              />
            </label>
            <label>
              Participants (comma separated)
              <input
                type="text"
                value={comparativeForm.participants}
                onChange={(event) => setComparativeForm((prev) => ({ ...prev, participants: event.target.value }))}
                placeholder="Augustine, Luther, Calvin"
                required
                style={{ width: "100%" }}
              />
            </label>
          </>
        )}

        <button type="submit" disabled={isRunning}>
          {isRunning ? "Running." : "Run workflow"}
        </button>
      </form>

      <style jsx>{`
        .workflow-button {
          border-radius: 0.75rem;
          padding: 0.75rem 1rem;
          border: 1px solid #cbd5f5;
          background: #fff;
          cursor: pointer;
          display: grid;
          gap: 0.35rem;
          text-align: left;
          position: relative;
          outline: 3px solid transparent;
          outline-offset: 2px;
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
        <p role="alert" style={{ color: "crimson", marginTop: "1rem" }}>
          {error}
        </p>
      )}

      {result && (
        <section style={{ marginTop: "2rem", background: "#fff", padding: "1.5rem", borderRadius: "0.75rem" }}>
          <p style={{ marginTop: 0, marginBottom: "1rem", color: "#4b5563" }}>
            {formatEmphasisSummary(mode)}
          </p>
          {result.kind === "verse" && (
            <>
              <h3>Verse brief for {result.payload.osis}</h3>
              {renderRAGAnswer(result.payload.answer, {
                followUps: result.payload.follow_ups,
                onExport: handleCitationExport,
                exporting: isSendingCitations,
                status: citationExportStatus,
              })}
            </>
          )}
          {result.kind === "sermon" && (
            <>
              <h3>Sermon prep: {result.payload.topic}</h3>
              {result.payload.osis && <p>Anchored to {result.payload.osis}</p>}
              <h4>Outline</h4>
              <ul>
          {result.kind === "multimedia" && (
            <>
              <h3>Multimedia digest</h3>
              {result.payload.collection && (
                <p>Collection: {result.payload.collection}</p>
              )}
              <h4>Highlights</h4>
              <ul>
                {result.payload.highlights.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              {renderRAGAnswer(result.payload.answer, {
                onExport: handleCitationExport,
                exporting: isSendingCitations,
                status: citationExportStatus,
              })}
            </>
          )}
          {result.kind === "devotional" && (
            <>
              <h3>Devotional guide for {result.payload.osis}</h3>
              <p>Focus: {result.payload.focus}</p>
              <h4>Reflection prompts</h4>
              <pre style={{ background: "#f9fafb", padding: "0.75rem", whiteSpace: "pre-wrap" }}>
                {result.payload.reflection}
              </pre>
              <h4>Prayer</h4>
              <pre style={{ background: "#f9fafb", padding: "0.75rem", whiteSpace: "pre-wrap" }}>
                {result.payload.prayer}
              </pre>
              {renderRAGAnswer(result.payload.answer, {
                onExport: handleCitationExport,
                exporting: isSendingCitations,
                status: citationExportStatus,
              })}
            </>
          )}
          {result.kind === "collaboration" && (
            <>
              <h3>Collaboration synthesis — {result.payload.thread}</h3>
              <pre style={{ background: "#f9fafb", padding: "0.75rem", whiteSpace: "pre-wrap" }}>
                {result.payload.synthesized_view}
              </pre>
              {renderRAGAnswer(result.payload.answer, {
                onExport: handleCitationExport,
                exporting: isSendingCitations,
                status: citationExportStatus,
              })}
            </>
          )}
          {result.kind === "curation" && (
            <>
              <h3>Corpus curation report</h3>
              <p>Effective since: {result.payload.since}</p>
              <p>Documents processed: {result.payload.documents_processed}</p>
              <h4>Summaries</h4>
              <ul>
                {result.payload.summaries.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </>
          )}
          {result.kind === "export" && (
            <>
              <h3>Export preset: {result.payload.label}</h3>
              <p>
                Format: {result.payload.format}
                {result.payload.filename ? ` · Filename: ${result.payload.filename}` : ""}
              </p>
              {result.payload.mediaType && <p>Media type: {result.payload.mediaType}</p>}
              <details>
                <summary>Preview content</summary>
                <pre style={{ background: "#f9fafb", padding: "0.75rem", whiteSpace: "pre-wrap" }}>
                  {result.payload.content}
                </pre>
              </details>
            </>
          )}
                {result.payload.outline.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <h4>Key points</h4>
              <ul>
                {result.payload.key_points.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              {renderRAGAnswer(result.payload.answer, {
                onExport: handleCitationExport,
                exporting: isSendingCitations,
                status: citationExportStatus,
              })}
            </>
          )}
          {result.kind === "comparative" && (
            <>
              <h3>Comparative analysis ({result.payload.osis})</h3>
              <p>Participants: {result.payload.participants.join(", ")}</p>
              <h4>Comparisons</h4>
              <ul>
                {result.payload.comparisons.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              {renderRAGAnswer(result.payload.answer, {
                onExport: handleCitationExport,
                exporting: isSendingCitations,
                status: citationExportStatus,
              })}
            </>
          )}
        </section>
      )}
    </section>
  );
}
