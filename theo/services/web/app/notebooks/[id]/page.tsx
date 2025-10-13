import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import Breadcrumbs from "../../components/Breadcrumbs";
import DeliverableExportAction, {
  type DeliverableRequestPayload,
} from "../../components/DeliverableExportAction";
import NotebookRealtimeListener from "../../components/NotebookRealtimeListener";
import { getApiBaseUrl } from "../../lib/api";
import ResearchPanels from "../../research/ResearchPanels";
import { fetchResearchFeatures } from "../../research/features";
import type { ResearchFeatureFlags } from "../../research/types";
import styles from "./page.module.css";

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
    <article key={entry.id} className={styles.entry}>
      <header className={styles.entryHeader}>
        <div>
          <h3 className={styles.entryHeading}>Entry</h3>
          <p className={styles.entryMeta}>
            Authored by <strong>{entry.created_by}</strong> on {new Date(entry.created_at).toLocaleString()}
          </p>
        </div>
        {entry.osis_ref ? (
          <span className={styles.entryLink}>
            Linked to <strong>{entry.osis_ref}</strong>
          </span>
        ) : null}
      </header>

      <p className={styles.entryBody}>{entry.content}</p>

      {entry.document_id ? (
        <footer className={styles.entryFooter}>
          <span className={styles.entryFooterLabel}>Source document:</span>
          <Link href={`/doc/${entry.document_id}`} className={styles.entryFooterLink}>
            View document {entry.document_id}
          </Link>
        </footer>
      ) : null}

      {mentions.length > 0 ? (
        <section>
          <h4 className={styles.mentionsHeading}>Mentions</h4>
          <ul className={styles.mentionsList}>
            {mentions.map((mention) => (
              <li key={mention.id}>
                <div className={styles.mentionText}>
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
  const { features: fetchedFeatures, error: researchFeaturesError } = osisRefs.length
    ? await fetchResearchFeatures()
    : { features: null, error: null };
  const features: ResearchFeatureFlags | null = fetchedFeatures;
  const featureDiscoveryFailed = Boolean(researchFeaturesError);
  if (researchFeaturesError) {
    console.error("Failed to fetch research features", researchFeaturesError);
  }
  const version = await fetchRealtimeVersion(notebook.id);

  const exportPayload: DeliverableRequestPayload | null = notebook.primary_osis
    ? {
        type: "sermon",
        osis: notebook.primary_osis,
        formats: ["markdown"],
      }
    : null;

  const hasReferencedVerses = osisRefs.length > 0;
  const showResearchSection = hasReferencedVerses || featureDiscoveryFailed;

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div className={styles.headerSummary}>
          <div>
            <p className={styles.meta}>Notebook ID: {notebook.id}</p>
            <h1 className={styles.title}>{notebook.title}</h1>
            <p className={styles.subtitle}>
              Created by {notebook.created_by} on {new Date(notebook.created_at).toLocaleString()}
            </p>
          </div>
          <NotebookRealtimeListener notebookId={notebook.id} initialVersion={version} />
        </div>
        {notebook.description ? <p className={styles.description}>{notebook.description}</p> : null}
        {exportPayload ? (
          <DeliverableExportAction
            label="Export sermon outline"
            requestPayload={exportPayload}
            idleText="Generate a sermon outline using this notebook's primary verse."
          />
        ) : null}
      </header>

      <section className={styles.section}>
        <h2 className={styles.sectionHeading}>Entries ({notebook.entry_count})</h2>
        {notebook.entries.length === 0 ? (
          <p className={styles.emptyState}>
            No entries have been added yet. Start collaborating by creating the first note.
          </p>
        ) : (
          <div className={styles.entriesList}>{notebook.entries.map((entry) => renderEntry(entry))}</div>
        )}
      </section>

      {showResearchSection ? (
        <section className={styles.section}>
          {hasReferencedVerses ? (
            <header className={styles.sectionHeader}>
              <h2 className={styles.sectionHeading}>Verse Aggregator</h2>
              <p className={styles.sectionDescription}>
                Collating insights for {osisRefs.join(", ")}
              </p>
            </header>
          ) : null}

          {featureDiscoveryFailed ? (
            <p role="alert" className={styles.researchAlert}>
              Unable to load research capabilities. {researchFeaturesError}
            </p>
          ) : null}

          {features
            ? osisRefs.map((osis) => (
                <div key={osis} className={styles.featureGroup}>
                  <h3 className={styles.featureHeading}>{osis}</h3>
                  <Suspense fallback={<p>Loading research panels…</p>}>
                    <ResearchPanels osis={osis} features={features} />
                  </Suspense>
                </div>
              ))
            : !researchFeaturesError && hasReferencedVerses ? (
                <p className={styles.researchFallback}>
                  Research capabilities are unavailable for this notebook.
                </p>
              ) : null}
        </section>
      ) : null}

      {notebook.collaborators.length > 0 ? (
        <section className={styles.section}>
          <h2 className={styles.sectionHeading}>Collaborators</h2>
          <ul className={styles.collaboratorList}>
            {notebook.collaborators.map((collaborator) => (
              <li key={collaborator.id} className={styles.collaboratorItem}>
                <div>
                  <strong>{collaborator.subject}</strong>
                  <p className={styles.collaboratorMeta}>
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
