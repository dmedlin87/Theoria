import Link from "next/link";
import { notFound } from "next/navigation";

import { formatAnchor, getApiBaseUrl } from "../../lib/api";

interface DocumentPageProps {
  params: { id: string };
  searchParams?: Record<string, string | string[] | undefined>;
}

interface Passage {
  id: string;
  document_id: string;
  text: string;
  osis_ref?: string | null;
  page_no?: number | null;
  t_start?: number | null;
  t_end?: number | null;
  meta?: Record<string, unknown> | null;
}

interface DocumentDetail {
  id: string;
  title?: string | null;
  source_type?: string | null;
  collection?: string | null;
  authors?: string[] | null;
  created_at: string;
  updated_at: string;
  source_url?: string | null;
  channel?: string | null;
  video_id?: string | null;
  duration_seconds?: number | null;
  meta?: Record<string, unknown> | null;
  passages: Passage[];
}

async function fetchDocument(id: string): Promise<DocumentDetail> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const response = await fetch(`${baseUrl}/documents/${id}`, { cache: "no-store" });
  if (response.status === 404) {
    notFound();
  }
  if (!response.ok) {
    throw new Error(`Failed to load document: ${response.statusText}`);
  }
  return (await response.json()) as DocumentDetail;
}

function formatAuthors(authors?: string[] | null): string | null {
  if (!authors || authors.length === 0) {
    return null;
  }
  return authors.join(", ");
}

export default async function DocumentPage({ params, searchParams }: DocumentPageProps) {
  const document = await fetchDocument(params.id);
  const initialPage = typeof searchParams?.page === "string" ? searchParams?.page : undefined;
  const initialTime = typeof searchParams?.t === "string" ? searchParams?.t : undefined;

  return (
    <section>
      <h2>{document.title ?? "Document"}</h2>
      <p>Document ID: {document.id}</p>
      <div style={{ margin: "1rem 0", display: "grid", gap: "0.5rem" }}>
        {document.source_url && (
          <a href={document.source_url} target="_blank" rel="noopener noreferrer">
            Original source
          </a>
        )}
        {document.collection && <p>Collection: {document.collection}</p>}
        {document.source_type && <p>Source type: {document.source_type}</p>}
        {formatAuthors(document.authors) && <p>Authors: {formatAuthors(document.authors)}</p>}
        {document.channel && <p>Channel: {document.channel}</p>}
        {initialPage && <p>Jumped to page {initialPage}</p>}
        {initialTime && <p>Jumped to timestamp {initialTime}s</p>}
      </div>

      <h3>Passages</h3>
      {document.passages.length === 0 ? (
        <p>No passages available for this document.</p>
      ) : (
        <ol style={{ padding: 0, listStyle: "none", display: "grid", gap: "1rem" }}>
          {document.passages.map((passage) => {
            const anchor = formatAnchor({
              page_no: passage.page_no ?? undefined,
              t_start: passage.t_start ?? undefined,
              t_end: passage.t_end ?? undefined,
            });
            return (
              <li
                key={passage.id}
                id={`passage-${passage.id}`}
                style={{ background: "#fff", padding: "1rem", borderRadius: "0.5rem" }}
              >
                <article>
                  <header>
                    {anchor && <p style={{ margin: "0 0 0.5rem" }}>{anchor}</p>}
                    {passage.osis_ref && (
                      <p style={{ margin: 0 }}>
                        Verse reference: <Link href={`/verse/${passage.osis_ref}`}>{passage.osis_ref}</Link>
                      </p>
                    )}
                  </header>
                  <p style={{ marginTop: "0.75rem", whiteSpace: "pre-wrap" }}>{passage.text}</p>
                </article>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
