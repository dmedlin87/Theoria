"use client";

import Link from "next/link";
import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";

import Breadcrumbs from "../../components/Breadcrumbs";
import VirtualList from "../../components/VirtualList";

import DeliverableExportAction from "../../components/DeliverableExportAction";
import styles from "./DocumentClient.module.css";
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
  } catch {
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

  // Using CSS custom properties for theme compatibility
  const typeBadgeStyles: Record<DocumentAnnotationType, { background: string; color: string }> = {
    claim: { background: "var(--color-warning)", color: "var(--color-text-inverse)" },
    evidence: { background: "var(--color-accent)", color: "var(--color-text-inverse)" },
    question: { background: "var(--color-info)", color: "var(--color-text-inverse)" },
    note: { background: "var(--color-text-muted)", color: "var(--color-text-primary)" },
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
      <Breadcrumbs
        items={[
          { label: "Home", href: "/" },
          { label: "Documents" },
          { label: document.title ?? "Document" },
        ]}
      />
      <h2>{document.title ?? "Document"}</h2>
      <p>Document ID: {document.id}</p>

      <details open className={styles.detailsSection}>
        <summary className={styles.detailsSummary}>Read & annotate</summary>
        <div className={styles.detailsContent}>
          <div className={styles.metaGrid}>
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

          <section aria-labelledby="document-annotations-heading">
            <h2 id="document-annotations-heading">Annotations</h2>
            <form onSubmit={handleAnnotationSubmit} className={styles.annotationForm}>
              <textarea
                name="annotation"
                ref={annotationTextareaRef}
                value={newAnnotation}
                onChange={(event) => setNewAnnotation(event.target.value)}
                rows={3}
                placeholder="Add a researcher note"
                className={styles.annotationTextarea}
              />
              <div className={styles.formActions}>
                <button type="submit" disabled={isSavingAnnotation}>
                  {isSavingAnnotation ? "Saving." : "Add annotation"}
                </button>
                {annotationError && (
                  <span role="alert" className={styles.errorText}>
                    {annotationError}
                  </span>
                )}
              </div>
            </form>
            {document.annotations.length === 0 ? (
              <p className={styles.noResults}>No annotations yet.</p>
            ) : (
              <ul className={styles.annotationsList}>
                {document.annotations.map((annotation) => {
              const badges = (
                <div className={styles.annotationBadges}>
                  <span className={`${styles.annotationBadge} ${styles[`annotationBadge--${annotation.type}`]}`}>
                    {typeLabels[annotation.type]}
                  </span>
                  {annotation.stance ? (
                    <span className={styles.annotationStance}>
                      {annotation.stance}
                    </span>
                  ) : null}
                </div>
              );

              return (
                <li
                  key={annotation.id}
                  className={styles.annotationCard}
                >
                  {badges}
                  <p className={styles.annotationBody}>{annotation.body}</p>
                  {annotation.passage_ids.length > 0 ? (
                    <div className={styles.linkedPassages}>
                      <span className={styles.linkedPassagesLabel}>Linked passages</span>
                      <ul className={styles.linkedPassagesList}>
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
                                className={styles.passageLink}
                              >
                                {anchorLabel || `Passage ${index + 1}`}
                              </Link>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  ) : null}
                  <div className={styles.annotationFooter}>
                    <span>{formatTimestamp(annotation.updated_at)}</span>
                    <button
                      type="button"
                      onClick={() => handleDeleteAnnotation(annotation.id)}
                      className={styles.deleteButton}
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
            <div className={styles.passagesHeader}>
              <h2 className={styles.passagesHeading}>Passages</h2>
              <button
                type="button"
                onClick={handleAddAnnotationShortcut}
                className={styles.addAnnotationButton}
              >
                Add annotation
              </button>
            </div>
            {document.passages.length === 0 ? (
              <p className={styles.noResults}>No passages available for this document.</p>
            ) : (
              <VirtualList
                items={document.passages}
                itemKey={(passage) => passage.id}
                estimateSize={() => 260}
                containerProps={{
                  className: "document-passages__list",
                  role: "list",
                  "aria-label": "Document passages",
                }}
                renderItem={(passage, index) => {
                  const anchor = formatAnchor({
                    page_no: passage.page_no ?? null,
                    t_start: passage.t_start ?? null,
                    t_end: passage.t_end ?? null,
                  });
                  return (
                    <div
                      id={`passage-${passage.id}`}
                      role="listitem"
                      className="document-passages__item"
                      data-last={index === document.passages.length - 1}
                    >
                      <article>
                        <header className={styles.passageHeader}>
                          {anchor && <p className={styles.passageMeta}>{anchor}</p>}
                          {passage.osis_ref && (
                            <p className={styles.passageMeta}>
                              Verse reference: <Link href={`/verse/${passage.osis_ref}`}>{passage.osis_ref}</Link>
                            </p>
                          )}
                        </header>
                        <p className={styles.passageText}>{passage.text}</p>
                      </article>
                    </div>
                  );
                }}
              />
            )}
          </section>
        </div>
      </details>

      <details className={styles.detailsSection}>
        <summary className={styles.detailsSummary}>Exports</summary>
        <div className={styles.detailsContent}>
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

      <details className={styles.detailsSection}>
        <summary className={styles.detailsSummary}>Edit metadata</summary>
        <form
          onSubmit={handleMetadataSubmit}
          className={styles.metadataForm}
        >
          <fieldset disabled={isSavingMetadata} className={styles.metadataFieldset}>
            <label className={styles.formField}>
              <span className={styles.formLabel}>Title</span>
              <input
                type="text"
                name="title"
                value={metadataDraft.title}
                onChange={handleMetadataInputChange("title")}
                className={styles.formInput}
              />
            </label>
            <label className={styles.formField}>
              <span className={styles.formLabel}>Collection</span>
              <input
                type="text"
                name="collection"
                value={metadataDraft.collection}
                onChange={handleMetadataInputChange("collection")}
                className={styles.formInput}
              />
            </label>
            <label className={styles.formField}>
              <span className={styles.formLabel}>Authors (comma separated)</span>
              <input
                type="text"
                name="authors"
                value={metadataDraft.authors}
                onChange={handleMetadataInputChange("authors")}
                className={styles.formInput}
              />
            </label>
            <label className={styles.formField}>
              <span className={styles.formLabel}>Source type</span>
              <input
                type="text"
                name="source_type"
                value={metadataDraft.sourceType}
                onChange={handleMetadataInputChange("sourceType")}
                className={styles.formInput}
              />
            </label>
            <label className={styles.formField}>
              <span className={styles.formLabel}>Abstract</span>
              <textarea
                name="abstract"
                value={metadataDraft.abstract}
                onChange={handleMetadataInputChange("abstract")}
                rows={4}
                className={styles.formTextarea}
              />
            </label>
            <div className={styles.formActions}>
              <button type="submit">{isSavingMetadata ? "Saving." : "Save changes"}</button>
              {lastMetadataSnapshot && !isSavingMetadata && (
                <button type="button" onClick={handleMetadataUndo}>
                  Undo last save
                </button>
              )}
            </div>
          </fieldset>
          {metadataMessage && (
            <p role="status" className={styles.statusMessage}>
              {metadataMessage}
            </p>
          )}
          {metadataError && (
            <p role="alert" className={`${styles.statusMessage} ${styles.errorText}`}>
              {metadataError}
            </p>
          )}
        </form>
      </details>
    </section>
  );
}
