"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { getApiBaseUrl } from "../lib/api";

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

function extractFilename(disposition: string | null): string | null {
  if (!disposition) {
    return null;
  }
  const match = disposition.match(/filename="?([^";]+)"?/i);
  return match ? match[1] : null;
}

function renderCitations(citations: RAGCitation[]): JSX.Element | null {
  if (!citations.length) {
    return null;
  }
  return (
    <div style={{ marginTop: "1rem" }}>
      <h4>Citations</h4>
      <ol style={{ paddingLeft: "1.25rem" }}>
        {citations.map((citation) => (
          <li key={citation.index} style={{ marginBottom: "0.5rem" }}>
            <strong>{citation.osis}</strong> ({citation.anchor}) — {citation.snippet}
          </li>
        ))}
      </ol>
    </div>
  );
}

function renderRAGAnswer(answer: RAGAnswer, followUps?: string[]): JSX.Element {
  return (
    <div style={{ marginTop: "1.5rem" }}>
      <h4>Answer</h4>
      <p>{answer.summary}</p>
      {renderCitations(answer.citations)}
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
  const [verseForm, setVerseForm] = useState({ osis: "", question: "" });
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

  const baseUrl = useMemo(() => getApiBaseUrl().replace(/\/$/, ""), []);

  useEffect(() => {
    let isMounted = true;
    const fetchFeatures = async () => {
      try {
        const response = await fetch(`${baseUrl}/features`, { cache: "no-store" });
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

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsRunning(true);
    setError(null);
    setResult(null);

    try {
      let response: Response;
      if (workflow === "verse") {
        if (!verseForm.osis.trim()) {
          throw new Error("Provide an OSIS reference.");
        }
        response = await fetch(`${baseUrl}/ai/verse`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ osis: verseForm.osis.trim(), question: verseForm.question.trim() || null }),
        });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = (await response.json()) as VerseResponse;
        setResult({ kind: "verse", payload });
      } else if (workflow === "sermon") {
        if (!sermonForm.topic.trim()) {
          throw new Error("Provide a sermon topic.");
        }
        response = await fetch(`${baseUrl}/ai/sermon-prep`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            topic: sermonForm.topic.trim(),
            osis: sermonForm.osis.trim() || null,
          }),
        });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = (await response.json()) as SermonResponse;
        setResult({ kind: "sermon", payload });
      } else if (workflow === "comparative") {
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
          body: JSON.stringify({ osis: comparativeForm.osis.trim(), participants }),
        });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = (await response.json()) as ComparativeResponse;
        setResult({ kind: "comparative", payload });
      } else if (workflow === "multimedia") {
        const collection = multimediaForm.collection.trim();
        response = await fetch(`${baseUrl}/ai/multimedia`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ collection: collection || null }),
        });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = (await response.json()) as MultimediaDigestResponse;
        setResult({ kind: "multimedia", payload });
      } else if (workflow === "devotional") {
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
          }),
        });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = (await response.json()) as DevotionalResponse;
        setResult({ kind: "devotional", payload });
      } else if (workflow === "collaboration") {
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
          }),
        });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = (await response.json()) as CollaborationResponse;
        setResult({ kind: "collaboration", payload });
      } else if (workflow === "curation") {
        const since = curationForm.since.trim();
        if (since && Number.isNaN(Date.parse(since))) {
          throw new Error("Provide an ISO 8601 timestamp (YYYY-MM-DD or similar).");
        }
        response = await fetch(`${baseUrl}/ai/curation`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ since: since || null }),
        });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = (await response.json()) as CorpusCurationReport;
        setResult({ kind: "curation", payload });
      } else if (workflow === "export") {
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
          };
        } else {
          url = `${baseUrl}/ai/transcript/export`;
          if (!exportForm.documentId.trim()) {
            throw new Error("Provide a document identifier to export.");
          }
          body = {
            document_id: exportForm.documentId.trim(),
            format: preset.format,
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
        const content = await response.text();
        const filename = extractFilename(response.headers.get("content-disposition"));
        setResult({
          kind: "export",
          payload: {
            preset: preset.id,
            label: preset.label,
            format: preset.format,
            filename,
            mediaType: response.headers.get("content-type"),
            content,
          },
        });
      } else {
        throw new Error("Unsupported workflow selected.");
      }
    } catch (requestError) {
      setError((requestError as Error).message || "Unable to run workflow");
    } finally {
      setIsRunning(false);
    }
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
            onClick={() => {
              setWorkflow(item.id);
              setError(null);
              setResult(null);
            }}
</p>
      </section>
    );
  }

  return (
    <section>
      <h2>Copilot</h2>
      <p>Run grounded workflows that stay anchored to your corpus.</p>

      <div style={{ display: "flex", gap: "0.75rem", margin: "1.5rem 0", flexWrap: "wrap" }}>
        {WORKFLOWS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setWorkflow(item.id)}
            style={{
              borderRadius: "0.75rem",
              padding: "0.75rem 1rem",
              border: workflow === item.id ? "2px solid #2563eb" : "1px solid #cbd5f5",
              background: workflow === item.id ? "#eff4ff" : "#fff",
              cursor: "pointer",
            }}
          >
            <strong style={{ display: "block" }}>{item.label}</strong>
            <span style={{ fontSize: "0.85rem", color: "#555" }}>{item.description}</span>
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} style={{ display: "grid", gap: "0.75rem", maxWidth: 600 }}>
        {workflow === "verse" && (
          <>
            <label>
              OSIS reference
              <input
                type="text"
                value={verseForm.osis}
                onChange={(event) => setVerseForm((prev) => ({ ...prev, osis: event.target.value }))}
                placeholder="John.1.1-5"
                required
                style={{ width: "100%" }}
              />
            </label>
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

      {error && (
        <p role="alert" style={{ color: "crimson", marginTop: "1rem" }}>
          {error}
        </p>
      )}

      {result && (
        <section style={{ marginTop: "2rem", background: "#fff", padding: "1.5rem", borderRadius: "0.75rem" }}>
          {result.kind === "verse" && (
            <>
              <h3>Verse brief for {result.payload.osis}</h3>
              {renderRAGAnswer(result.payload.answer, result.payload.follow_ups)}
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
              {renderRAGAnswer(result.payload.answer)}
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
              {renderRAGAnswer(result.payload.answer)}
            </>
          )}
          {result.kind === "collaboration" && (
            <>
              <h3>Collaboration synthesis — {result.payload.thread}</h3>
              <pre style={{ background: "#f9fafb", padding: "0.75rem", whiteSpace: "pre-wrap" }}>
                {result.payload.synthesized_view}
              </pre>
              {renderRAGAnswer(result.payload.answer)}
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
              {renderRAGAnswer(result.payload.answer)}
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
              {renderRAGAnswer(result.payload.answer)}
            </>
          )}
        </section>
      )}
    </section>
  );
}
