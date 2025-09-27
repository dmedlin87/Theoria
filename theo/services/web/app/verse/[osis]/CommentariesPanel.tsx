import { getApiBaseUrl } from "../../lib/api";
import type { ResearchFeatureFlags } from "./research-panels";

type ResearchEvidence = {
  id?: string;
  source_type?: string | null;
  source_ref?: string | null;
  citation?: string | null;
  snippet?: string | null;
  osis_refs?: string[] | null;
};

type ResearchNote = {
  id: string;
  title?: string | null;
  body: string;
  stance?: string | null;
  claim_type?: string | null;
  confidence?: number | null;
  tags?: string[] | null;
  evidences?: ResearchEvidence[] | null;
  created_at?: string | null;
  updated_at?: string | null;
};

type ResearchNotesResponse = {
  osis: string;
  notes?: ResearchNote[] | null;
  total?: number | null;
};

interface CommentariesPanelProps {
  osis: string;
  features: ResearchFeatureFlags;
}

export default async function CommentariesPanel({
  osis,
  features,
}: CommentariesPanelProps) {
  if (!features?.commentaries) {
    return null;
  }

  const baseUrl = getApiBaseUrl().replace(/\/$/, "");

  let notes: ResearchNote[] = [];
  let error: string | null = null;

  try {
    const response = await fetch(
      `${baseUrl}/research/notes?osis=${encodeURIComponent(osis)}`,
      { cache: "no-store" },
    );
    if (!response.ok) {
      throw new Error((await response.text()) || response.statusText);
    }
    const payload = (await response.json()) as ResearchNotesResponse;
    notes = payload.notes?.filter((note): note is ResearchNote => Boolean(note)) ?? [];
  } catch (fetchError) {
    console.error("Failed to load commentaries", fetchError);
    error = fetchError instanceof Error ? fetchError.message : "Unknown error";
  }

  return (
    <section
      aria-labelledby="commentaries-heading"
      style={{
        background: "#fff",
        borderRadius: "0.5rem",
        padding: "1rem",
        boxShadow: "0 1px 2px rgba(15, 23, 42, 0.08)",
      }}
    >
      <h3 id="commentaries-heading" style={{ marginTop: 0 }}>
        Commentaries & notes
      </h3>
      <p style={{ margin: "0 0 1rem", color: "var(--muted-foreground, #4b5563)" }}>
        Curated research notes anchored to <strong>{osis}</strong>.
      </p>
      {error ? (
        <p role="alert" style={{ color: "var(--danger, #b91c1c)" }}>
          Unable to load commentaries. {error}
        </p>
      ) : notes.length === 0 ? (
        <p>No commentaries recorded yet.</p>
      ) : (
        <ul
          style={{
            listStyle: "none",
            padding: 0,
            margin: 0,
            display: "grid",
            gap: "1rem",
          }}
        >
          {notes.map((note) => (
            <li
              key={note.id}
              style={{
                border: "1px solid var(--border, #e5e7eb)",
                borderRadius: "0.5rem",
                padding: "0.75rem",
              }}
            >
              <header style={{ marginBottom: "0.5rem" }}>
                <h4 style={{ margin: "0 0 0.25rem" }}>{note.title ?? "Untitled note"}</h4>
                <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--muted-foreground, #4b5563)" }}>
                  {note.stance ? `${note.stance} perspective` : "Perspective not set"}
                  {note.claim_type ? ` · ${note.claim_type}` : ""}
                  {typeof note.confidence === "number"
                    ? ` · Confidence ${(note.confidence * 100).toFixed(0)}%`
                    : ""}
                </p>
                {note.tags && note.tags.length > 0 ? (
                  <p style={{ margin: "0.25rem 0 0", fontSize: "0.75rem", color: "var(--muted-foreground, #4b5563)" }}>
                    Tags: {note.tags.join(", ")}
                  </p>
                ) : null}
              </header>
              <p style={{ margin: "0 0 0.5rem", lineHeight: 1.6 }}>{note.body}</p>
              {note.evidences && note.evidences.length > 0 ? (
                <ul
                  style={{
                    margin: 0,
                    paddingLeft: "1.25rem",
                    color: "var(--muted-foreground, #4b5563)",
                    fontSize: "0.875rem",
                  }}
                >
                  {note.evidences.map((evidence, index) => (
                    <li key={evidence.id ?? `${note.id}-evidence-${index}`} style={{ marginBottom: "0.5rem" }}>
                      {evidence.snippet ? (
                        <blockquote style={{ margin: "0 0 0.25rem" }}>
                          {evidence.snippet}
                        </blockquote>
                      ) : null}
                      <span>
                        {evidence.source_type ? `${evidence.source_type}: ` : ""}
                        {evidence.source_ref ?? "Unspecified source"}
                      </span>
                      {evidence.osis_refs && evidence.osis_refs.length > 0 ? (
                        <span> · {evidence.osis_refs.join(", ")}</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
