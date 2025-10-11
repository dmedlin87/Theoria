"use client";

import Link from "next/link";
import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";

import DeliverableExportAction from "../../components/DeliverableExportAction";
import { buildPassageLink, formatAnchor, getApiBaseUrl } from "../../lib/api";
import type {
  DocumentAnnotation,
  DocumentAnnotationType,
  DocumentDetail,
  Passage,
} from "./types";

interface Props {
  initialDocument: DocumentDetail;
}

interface MetadataDraft {
  title: string;
  collection: string;
  authors: string;
  sourceType: string;
  abstract: string;
}

interface MetadataSnapshot {
  title: string;
  collection: string;
  authors: string[];
  source_type: string | null;
  abstract: string | null;
}

const SAFE_SOURCE_URL_PROTOCOLS = new Set(["http", "https"]);

function isSafeSourceUrl(url?: string | null): boolean {
  if (!url) {
    return false;
  }
  if (url.startsWith("/")) {
    return true;
  }
  try {
    const parsed = new URL(url);
    const protocol = parsed.protocol.replace(/:$/, "").toLowerCase();
    return SAFE_SOURCE_URL_PROTOCOLS.has(protocol);
  } catch (error) {
    return false;
  }
}

function formatAuthors(authors?: string[] | null): string {
  return (authors ?? []).join(", ");
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString();
}

export default function DocumentClient({ initialDocument }: Props): JSX.Element {
  const [document, setDocument] = useState<DocumentDetail>(initialDocument);
  const [isSavingMetadata, setIsSavingMetadata] = useState(false);
  const [metadataMessage, setMetadataMessage] = useState<string | null>(null);
  const [metadataError, setMetadataError] = useState<string | null>(null);
  const [lastMetadataSnapshot, setLastMetadataSnapshot] = useState<MetadataSnapshot | null>(null);

  const [metadataDraft, setMetadataDraft] = useState<MetadataDraft>(() => ({
    title: initialDocument.title ?? "",
    collection: initialDocument.collection ?? "",
    authors: formatAuthors(initialDocument.authors),
    sourceType: initialDocument.source_type ?? "",
    abstract: initialDocument.abstract ?? "",
  }));

  const [newAnnotation, setNewAnnotation] = useState("");
  const [isSavingAnnotation, setIsSavingAnnotation] = useState(false);
  const [annotationError, setAnnotationError] = useState<string | null>(null);

  const annotationTextareaRef = useRef<HTMLTextAreaElement | null>(null);

  const baseUrl = useMemo(() => getApiBaseUrl().replace(/\/$/, ""), []);
  const passageLookup = useMemo(() => {
    const lookup = new Map<string, Passage>();
    for (const passage of document.passages) {
      lookup.set(passage.id, passage);
    }
    return lookup;
  }, [document.passages]);

  const typeLabels: Record<DocumentAnnotationType, string> = {
    claim: "Claim",
    evidence: "Evidence",
    question: "Question",
    note: "Note",
  };

  const typeBadgeStyles: Record<DocumentAnnotationType, { background: string; color: string }> = {
    claim: { background: "#f97316", color: "#fff" },
    evidence: { background: "#2563eb", color: "#fff" },
    question: { background: "#14b8a6", color: "#fff" },
    note: { background: "#94a3b8", color: "#111827" },
  };

  useEffect(() => {
    setMetadataDraft({
      title: document.title ?? "",
      collection: document.collection ?? "",
      authors: formatAuthors(document.authors),
      sourceType: document.source_type ?? "",
      abstract: document.abstract ?? "",
    });
  }, [document]);

  const handleMetadataInputChange = (field: keyof MetadataDraft) =>
    (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      setMetadataDraft((prev) => ({ ...prev, [field]: event.target.value }));
      setMetadataMessage(null);
      setMetadataError(null);
    };

  const handleMetadataSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMetadataError(null);
    setMetadataMessage(null);

    const title = metadataDraft.title.trim();
    const collection = metadataDraft.collection.trim();
    const authorsRaw = metadataDraft.authors.trim();
    const sourceType = metadataDraft.sourceType.trim();
    const abstract = metadataDraft.abstract.trim();

    const authors = authorsRaw
      ? authorsRaw.split(",").map((value) => value.trim()).filter(Boolean)
      : [];

    const previousMetadata: MetadataSnapshot = {
      title: document.title ?? "",
      collection: document.collection ?? "",
      authors: document.authors ?? [],
      source_type: document.source_type ?? null,
      abstract: document.abstract ?? null,
    };

    const nextMetadata: MetadataSnapshot = {
      title,
      collection,
      authors,
      source_type: sourceType || null,
      abstract: abstract || null,
    };

    const normalizeAuthors = (values: string[]): string[] =>
      values.map((value) => value.trim()).filter(Boolean);

    const previousAuthors = normalizeAuthors(previousMetadata.authors);
    const nextAuthors = normalizeAuthors(nextMetadata.authors);

    const authorsMatch =
      previousAuthors.length === nextAuthors.length &&
      previousAuthors.every((value, index) => value === nextAuthors[index]);

    const metadataUnchanged =
      nextMetadata.title === previousMetadata.title &&
      nextMetadata.collection === previousMetadata.collection &&
      authorsMatch &&
      nextMetadata.source_type === previousMetadata.source_type &&
      nextMetadata.abstract === previousMetadata.abstract;

    if (metadataUnchanged) {
      setMetadataMessage("No changes to save");
      return;
    }

    setIsSavingMetadata(true);

    try {
      const response = await fetch(`${baseUrl}/documents/${document.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(nextMetadata),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const updated = (await response.json()) as DocumentDetail;
      setDocument(updated);
      setMetadataMessage("Metadata saved");
      setLastMetadataSnapshot(previousMetadata);
    } catch (error) {
      setMetadataError((error as Error).message || "Unable to save metadata");
    } finally {
      setIsSavingMetadata(false);
    }
  };

  const handleMetadataUndo = async () => {
    if (!lastMetadataSnapshot) {
      return;
    }
    setIsSavingMetadata(true);
    setMetadataError(null);
    setMetadataMessage(null);

    try {
      const response = await fetch(`${baseUrl}/documents/${document.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: lastMetadataSnapshot.title,
          collection: lastMetadataSnapshot.collection,
          authors: lastMetadataSnapshot.authors,
          source_type: lastMetadataSnapshot.source_type,
          abstract: lastMetadataSnapshot.abstract,
        }),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const updated = (await response.json()) as DocumentDetail;
      setDocument(updated);
      setMetadataMessage("Changes reverted");
      setLastMetadataSnapshot(null);
    } catch (error) {
      setMetadataError((error as Error).message || "Unable to undo changes");
    } finally {
      setIsSavingMetadata(false);
    }
  };

  const handleAnnotationSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!newAnnotation.trim()) {
      setAnnotationError("Annotation cannot be empty");
      return;
    }
    setAnnotationError(null);
    setIsSavingAnnotation(true);
    try {
      const response = await fetch(`${baseUrl}/documents/${document.id}/annotations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: "note", text: newAnnotation.trim() }),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const created = (await response.json()) as DocumentAnnotation;
      setDocument((prev) => ({
        ...prev,
        annotations: [...prev.annotations, created],
      }));
      setNewAnnotation("");
    } catch (error) {
      setAnnotationError((error as Error).message || "Unable to save annotation");
    } finally {
      setIsSavingAnnotation(false);
    }
  };

  const handleAddAnnotationShortcut = () => {
    const element = annotationTextareaRef.current;
    if (element) {
      element.focus();
      element.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };

  const handleDeleteAnnotation = async (annotationId: string) => {
    setAnnotationError(null);
    try {
      const response = await fetch(
        `${baseUrl}/documents/${document.id}/annotations/${annotationId}`,
        {
          method: "DELETE",
        }
      );
      if (!response.ok) {
        throw new Error(await response.text());
      }
      setDocument((prev) => ({
        ...prev,
        annotations: prev.annotations.filter((annotation) => annotation.id !== annotationId),
      }));
    } catch (error) {
      setAnnotationError((error as Error).message || "Unable to delete annotation");
    }
  };

  return (
    <section>
      <h2>{document.title ?? "Document"}</h2>
      <p>Document ID: {document.id}</p>

      <details open style={{ margin: "1.5rem 0", border: "1px solid #e2e8f0", borderRadius: "0.75rem", padding: "1rem" }}>
        <summary style={{ fontSize: "1.125rem", fontWeight: 600, cursor: "pointer" }}>Read & annotate</summary>
        <div style={{ marginTop: "1rem", display: "grid", gap: "1.5rem" }}>
          <div style={{ display: "grid", gap: "0.35rem" }}>
            {document.source_url &&
              (isSafeSourceUrl(document.source_url) ? (
                <a href={document.source_url} target="_blank" rel="noopener noreferrer">
                  Original source
                </a>
              ) : (
                <span>Original source: {document.source_url}</span>
              ))}
            {document.collection && <p>Collection: {document.collection}</p>}
            {document.source_type && <p>Source type: {document.source_type}</p>}
            {document.authors && document.authors.length > 0 && <p>Authors: {formatAuthors(document.authors)}</p>}
            {document.channel && <p>Channel: {document.channel}</p>}
          </div>

          <section>
            <h3>Annotations</h3>
            <form onSubmit={handleAnnotationSubmit} style={{ display: "grid", gap: "0.5rem", maxWidth: 520 }}>
              <textarea
                name="annotation"
                ref={annotationTextareaRef}
                value={newAnnotation}
                onChange={(event) => setNewAnnotation(event.target.value)}
                rows={3}
                placeholder="Add a researcher note"
                style={{ width: "100%" }}
              />
              <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
                <button type="submit" disabled={isSavingAnnotation}>
                  {isSavingAnnotation ? "Saving." : "Add annotation"}
                </button>
                {annotationError && (
                  <span role="alert" style={{ color: "crimson" }}>
                    {annotationError}
                  </span>
                )}
              </div>
            </form>
            {document.annotations.length === 0 ? (
              <p style={{ marginTop: "1rem" }}>No annotations yet.</p>
            ) : (
              <ul style={{ listStyle: "none", margin: "1rem 0 0", padding: 0, display: "grid", gap: "0.75rem" }}>
                {document.annotations.map((annotation) => {
              const badgeStyle = typeBadgeStyles[annotation.type] ?? typeBadgeStyles.note;
              const badges = (
                <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.5rem" }}>
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      fontSize: "0.75rem",
                      padding: "0.125rem 0.5rem",
                      borderRadius: "999px",
                      fontWeight: 600,
                      background: badgeStyle.background,
                      color: badgeStyle.color,
                      textTransform: "uppercase",
                      letterSpacing: "0.03em",
                    }}
                  >
                    {typeLabels[annotation.type]}
                  </span>
                  {annotation.stance ? (
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        fontSize: "0.75rem",
                        padding: "0.125rem 0.5rem",
                        borderRadius: "999px",
                        fontWeight: 600,
                        background: "#f8fafc",
                        color: "#0f172a",
                        border: "1px solid #cbd5f5",
                        letterSpacing: "0.03em",
                      }}
                    >
                      {annotation.stance}
                    </span>
                  ) : null}
                </div>
              );

              return (
                <li
                  key={annotation.id}
                  style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: "0.5rem", padding: "0.75rem" }}
                >
                  {badges}
                  <p style={{ margin: "0 0 0.5rem", whiteSpace: "pre-wrap" }}>{annotation.body}</p>
                  {annotation.passage_ids.length > 0 ? (
                    <div style={{ marginBottom: "0.5rem" }}>
                      <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "#475569" }}>Linked passages</span>
                      <ul style={{ margin: "0.25rem 0 0", paddingLeft: "1rem", display: "grid", gap: "0.25rem" }}>
                        {annotation.passage_ids.map((passageId, index) => {
                          const passage = passageLookup.get(passageId);
                          const anchorLabel = passage ? formatAnchor({
                            page_no: passage.page_no ?? null,
                            t_start: passage.t_start ?? null,
                            t_end: passage.t_end ?? null,
                          }) : null;
                          const href = buildPassageLink(document.id, passageId, {
                            pageNo: passage?.page_no ?? null,
                            tStart: passage?.t_start ?? null,
                          });
                          return (
                            <li key={`${annotation.id}-passage-${passageId}-${index}`}>
                              <Link
                                href={href}
                                prefetch={false}
                                style={{ color: "#2563eb", textDecoration: "underline" }}
                              >
                                {anchorLabel || `Passage ${index + 1}`}
                              </Link>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  ) : null}
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      fontSize: "0.85rem",
                      color: "#555",
                    }}
                  >
                    <span>{formatTimestamp(annotation.updated_at)}</span>
                    <button
                      type="button"
                      onClick={() => handleDeleteAnnotation(annotation.id)}
                      style={{ color: "crimson", background: "none", border: "none", cursor: "pointer" }}
                    >
                      Delete
                    </button>
                  </div>
                </li>
              );
            })}
              </ul>
            )}
          </section>

          <section>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem" }}>
              <h3 style={{ margin: 0 }}>Passages</h3>
              <button
                type="button"
                onClick={handleAddAnnotationShortcut}
                style={{ padding: "0.5rem 0.85rem", borderRadius: "999px", border: "1px solid #2563eb", background: "#2563eb", color: "#fff" }}
              >
                Add annotation
              </button>
            </div>
            {document.passages.length === 0 ? (
              <p style={{ marginTop: "1rem" }}>No passages available for this document.</p>
            ) : (
              <ol style={{ padding: 0, listStyle: "none", display: "grid", gap: "1rem", marginTop: "1rem" }}>
                {document.passages.map((passage) => {
                  const anchor = formatAnchor({
                    page_no: passage.page_no ?? null,
                    t_start: passage.t_start ?? null,
                    t_end: passage.t_end ?? null,
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
        </div>
      </details>

      <details style={{ margin: "1.5rem 0", border: "1px solid #e2e8f0", borderRadius: "0.75rem", padding: "1rem" }}>
        <summary style={{ fontSize: "1.125rem", fontWeight: 600, cursor: "pointer" }}>Exports</summary>
        <div style={{ marginTop: "1rem" }}>
          <DeliverableExportAction
            label="Export Q&A digest"
            preparingText="Generating transcript digest…"
            successText="Transcript export ready."
            idleText="Download a digest for this transcript."
            requestPayload={{
              type: "transcript",
              document_id: document.id,
              formats: ["markdown", "csv"],
            }}
          />
        </div>
      </details>

      <details style={{ margin: "1.5rem 0", border: "1px solid #e2e8f0", borderRadius: "0.75rem", padding: "1rem" }}>
        <summary style={{ fontSize: "1.125rem", fontWeight: 600, cursor: "pointer" }}>Edit metadata</summary>
        <form
          onSubmit={handleMetadataSubmit}
          style={{ marginTop: "1rem", display: "grid", gap: "0.75rem", maxWidth: 560 }}
        >
          <fieldset disabled={isSavingMetadata} style={{ display: "grid", gap: "0.75rem" }}>
            <label>
              Title
              <input
                type="text"
                name="title"
                value={metadataDraft.title}
                onChange={handleMetadataInputChange("title")}
                style={{ width: "100%" }}
              />
            </label>
            <label>
              Collection
              <input
                type="text"
                name="collection"
                value={metadataDraft.collection}
                onChange={handleMetadataInputChange("collection")}
                style={{ width: "100%" }}
              />
            </label>
            <label>
              Authors (comma separated)
              <input
                type="text"
                name="authors"
                value={metadataDraft.authors}
                onChange={handleMetadataInputChange("authors")}
                style={{ width: "100%" }}
              />
            </label>
            <label>
              Source type
              <input
                type="text"
                name="source_type"
                value={metadataDraft.sourceType}
                onChange={handleMetadataInputChange("sourceType")}
                style={{ width: "100%" }}
              />
            </label>
            <label>
              Abstract
              <textarea
                name="abstract"
                value={metadataDraft.abstract}
                onChange={handleMetadataInputChange("abstract")}
                rows={4}
                style={{ width: "100%" }}
              />
            </label>
            <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
              <button type="submit">{isSavingMetadata ? "Saving." : "Save changes"}</button>
              {lastMetadataSnapshot && !isSavingMetadata && (
                <button type="button" onClick={handleMetadataUndo}>
                  Undo last save
                </button>
              )}
            </div>
          </fieldset>
          {metadataMessage && (
            <p role="status" style={{ margin: 0 }}>
              {metadataMessage}
            </p>
          )}
          {metadataError && (
            <p role="alert" style={{ color: "crimson", margin: 0 }}>
              {metadataError}
            </p>
          )}
        </form>
      </details>
    </section>
  );
}
