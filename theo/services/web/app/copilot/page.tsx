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

type CopilotResult =
  | { kind: "verse"; payload: VerseResponse }
  | { kind: "sermon"; payload: SermonResponse }
  | { kind: "comparative"; payload: ComparativeResponse };

type WorkflowId = "verse" | "sermon" | "comparative";

const WORKFLOWS: { id: WorkflowId; label: string; description: string }[] = [
  { id: "verse", label: "Verse brief", description: "Ask a grounded question anchored to a verse." },
  { id: "sermon", label: "Sermon prep", description: "Generate outlines and key points for a topic." },
  { id: "comparative", label: "Comparative analysis", description: "Compare viewpoints linked to an OSIS reference." },
];

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
      } else {
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
        <p>Loading</p>
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
