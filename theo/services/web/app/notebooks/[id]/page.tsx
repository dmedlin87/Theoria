import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import DeliverableExportAction, {
  type DeliverableRequestPayload,
} from "../../components/DeliverableExportAction";
import NotebookRealtimeListener from "../../components/NotebookRealtimeListener";
import { getApiBaseUrl } from "../../lib/api";
import ResearchPanels from "../../research/ResearchPanels";
import { fetchResearchFeatures } from "../../research/features";
import type { ResearchFeatureFlags } from "../../research/types";

interface NotebookCollaborator {
  id: string;
  subject: string;
  role: string;
  created_at: string;
}

interface NotebookEntryMention {
  id: string;
  osis_ref: string;
  document_id?: string | null;
  context?: string | null;
  created_at: string;
}

interface NotebookEntry {
  id: string;
  notebook_id: string;
  document_id?: string | null;
  osis_ref?: string | null;
  content: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  mentions: NotebookEntryMention[];
}

interface NotebookResponse {
  id: string;
  title: string;
  description?: string | null;
  team_id?: string | null;
  is_public: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
  primary_osis?: string | null;
  entry_count: number;
  entries: NotebookEntry[];
  collaborators: NotebookCollaborator[];
}

interface NotebookPageProps {
  params: { id: string };
}

async function fetchNotebook(id: string): Promise<NotebookResponse> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const response = await fetch(`${baseUrl}/notebooks/${encodeURIComponent(id)}`, {
    cache: "no-store",
  });
  if (response.status === 404) {
    notFound();
  }
  if (!response.ok) {
    throw new Error(`Unable to load notebook: ${response.statusText}`);
  }
  return (await response.json()) as NotebookResponse;
}

async function fetchRealtimeVersion(id: string): Promise<number> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const response = await fetch(
    `${baseUrl}/realtime/notebooks/${encodeURIComponent(id)}/poll`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    return 0;
  }
  const payload = (await response.json()) as { version?: number };
  return typeof payload.version === "number" ? payload.version : 0;
}

function collectOsis(notebook: NotebookResponse): string[] {
  const refs = new Set<string>();
  for (const entry of notebook.entries) {
    if (entry.osis_ref) {
      refs.add(entry.osis_ref);
    }
    for (const mention of entry.mentions) {
      if (mention.osis_ref) {
        refs.add(mention.osis_ref);
      }
    }
  }
  if (notebook.primary_osis) {
    refs.add(notebook.primary_osis);
  }
  return Array.from(refs);
}

function renderEntry(entry: NotebookEntry) {
  const mentions = entry.mentions ?? [];
  return (
    <article
      key={entry.id}
      style={{
        border: "1px solid var(--border, #e5e7eb)",
        borderRadius: "0.75rem",
        padding: "1rem",
        background: "var(--background, #ffffff)",
        display: "grid",
        gap: "0.75rem",
      }}
    >
      <header style={{ display: "flex", justifyContent: "space-between", gap: "1rem" }}>
        <div>
          <h3 style={{ margin: 0 }}>Entry</h3>
          <p style={{ margin: "0.25rem 0", color: "var(--muted-foreground, #4b5563)", fontSize: "0.85rem" }}>
            Authored by <strong>{entry.created_by}</strong> on {new Date(entry.created_at).toLocaleString()}
          </p>
        </div>
        {entry.osis_ref ? (
          <span style={{ fontSize: "0.9rem", color: "var(--muted-foreground, #4b5563)" }}>
            Linked to <strong>{entry.osis_ref}</strong>
          </span>
        ) : null}
      </header>

      <p style={{ margin: 0, whiteSpace: "pre-wrap", lineHeight: 1.5 }}>{entry.content}</p>

      {entry.document_id ? (
        <footer style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
          <span style={{ fontSize: "0.85rem", color: "var(--muted-foreground, #4b5563)" }}>
            Source document:
          </span>
          <Link href={`/doc/${entry.document_id}`} style={{ fontWeight: 500 }}>
            View document {entry.document_id}
          </Link>
        </footer>
      ) : null}

      {mentions.length > 0 ? (
        <section>
          <h4 style={{ margin: "0 0 0.5rem" }}>Mentions</h4>
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.5rem" }}>
            {mentions.map((mention) => (
              <li key={mention.id}>
                <div style={{ fontSize: "0.9rem", color: "var(--muted-foreground, #4b5563)" }}>
                  <strong>{mention.osis_ref}</strong>
                  {mention.context ? ` — ${mention.context}` : ""}
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </article>
  );
}

export default async function NotebookPage({ params }: NotebookPageProps) {
  const notebook = await fetchNotebook(params.id);
  const osisRefs = collectOsis(notebook);

  let features: ResearchFeatureFlags | null = null;
  let featureDiscoveryFailed = false;
  if (osisRefs.length) {
    try {
      features = await fetchResearchFeatures();
    } catch (error) {
      featureDiscoveryFailed = true;
      console.error("Failed to fetch research features", error);
      features = null;
    }
  }
  const version = await fetchRealtimeVersion(notebook.id);

  const exportPayload: DeliverableRequestPayload | null = notebook.primary_osis
    ? {
        type: "sermon",
        osis: notebook.primary_osis,
        formats: ["markdown"],
      }
    : null;

  return (
    <div style={{ display: "grid", gap: "2rem", padding: "1.5rem" }}>
      <header style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
          <div>
            <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--muted-foreground, #6b7280)" }}>
              Notebook ID: {notebook.id}
            </p>
            <h1 style={{ margin: "0.25rem 0" }}>{notebook.title}</h1>
            <p style={{ margin: 0, color: "var(--muted-foreground, #4b5563)" }}>
              Created by {notebook.created_by} on {new Date(notebook.created_at).toLocaleString()}
            </p>
          </div>
          <NotebookRealtimeListener notebookId={notebook.id} initialVersion={version} />
        </div>
        {notebook.description ? (
          <p style={{ margin: 0, fontSize: "1rem", lineHeight: 1.5 }}>{notebook.description}</p>
        ) : null}
        {exportPayload ? (
          <DeliverableExportAction
            label="Export sermon outline"
            requestPayload={exportPayload}
            idleText="Generate a sermon outline using this notebook's primary verse."
          />
        ) : null}
      </header>

      <section style={{ display: "grid", gap: "1rem" }}>
        <h2 style={{ margin: 0 }}>Entries ({notebook.entry_count})</h2>
        {notebook.entries.length === 0 ? (
          <p style={{ color: "var(--muted-foreground, #4b5563)" }}>
            No entries have been added yet. Start collaborating by creating the first note.
          </p>
        ) : (
          <div style={{ display: "grid", gap: "1.25rem" }}>
            {notebook.entries.map((entry) => renderEntry(entry))}
          </div>
        )}
      </section>

      {featureDiscoveryFailed ? (
        <p
          role="alert"
          style={{
            background: "var(--muted, #fef2f2)",
            color: "var(--muted-foreground, #b91c1c)",
            borderRadius: "0.5rem",
            padding: "0.75rem 1rem",
          }}
        >
          Research features are temporarily unavailable. Notebook entries remain accessible.
        </p>
      ) : null}

      {osisRefs.length > 0 && features ? (
        <section style={{ display: "grid", gap: "1.5rem" }}>
          <header>
            <h2 style={{ margin: 0 }}>Verse Aggregator</h2>
            <p style={{ margin: "0.25rem 0", color: "var(--muted-foreground, #4b5563)" }}>
              Collating insights for {osisRefs.join(", ")}
            </p>
          </header>
          {osisRefs.map((osis) => (
            <div key={osis} style={{ borderTop: "1px solid var(--border, #e5e7eb)", paddingTop: "1rem" }}>
              <h3 style={{ marginTop: 0 }}>{osis}</h3>
              <Suspense fallback={<p>Loading research panels…</p>}>
                <ResearchPanels osis={osis} features={features} />
              </Suspense>
            </div>
          ))}
        </section>
      ) : null}

      {notebook.collaborators.length > 0 ? (
        <section style={{ display: "grid", gap: "0.75rem" }}>
          <h2 style={{ margin: 0 }}>Collaborators</h2>
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.5rem" }}>
            {notebook.collaborators.map((collaborator) => (
              <li
                key={collaborator.id}
                style={{
                  background: "var(--muted, #f1f5f9)",
                  padding: "0.75rem",
                  borderRadius: "0.75rem",
                  display: "flex",
                  justifyContent: "space-between",
                  gap: "1rem",
                  alignItems: "center",
                }}
              >
                <div>
                  <strong>{collaborator.subject}</strong>
                  <p style={{ margin: 0, color: "var(--muted-foreground, #4b5563)", fontSize: "0.85rem" }}>
                    {collaborator.role} · Joined {new Date(collaborator.created_at).toLocaleDateString()}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
