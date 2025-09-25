"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

import { buildPassageLink, formatAnchor, getApiBaseUrl } from "../../lib/api";
import type { DocumentAnnotation, DocumentDetail } from "./types";

interface Props {
  initialDocument: DocumentDetail;
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

  const [newAnnotation, setNewAnnotation] = useState("");
  const [isSavingAnnotation, setIsSavingAnnotation] = useState(false);
  const [annotationError, setAnnotationError] = useState<string | null>(null);

  const baseUrl = useMemo(() => getApiBaseUrl().replace(/\/$/, ""), []);

  const handleMetadataSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSavingMetadata(true);
    setMetadataError(null);
    setMetadataMessage(null);

    const formData = new FormData(event.currentTarget);
    const title = (formData.get("title") as string | null)?.trim() ?? "";
    const collection = (formData.get("collection") as string | null)?.trim() ?? "";
    const authorsRaw = (formData.get("authors") as string | null)?.trim() ?? "";
    const sourceType = (formData.get("source_type") as string | null)?.trim() ?? "";
    const abstract = (formData.get("abstract") as string | null)?.trim() ?? "";

    const authors = authorsRaw
      ? authorsRaw.split(",").map((value) => value.trim()).filter(Boolean)
      : [];

    try {
      const response = await fetch(`${baseUrl}/documents/${document.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          collection,
          authors,
          source_type: sourceType || null,
          abstract: abstract || null,
        }),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const updated = (await response.json()) as DocumentDetail;
      setDocument(updated);
      setMetadataMessage("Metadata saved");
    } catch (error) {
      setMetadataError((error as Error).message || "Unable to save metadata");
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
        body: JSON.stringify({ body: newAnnotation.trim() }),
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

      <form onSubmit={handleMetadataSubmit} style={{ margin: "1.5rem 0", display: "grid", gap: "0.75rem", maxWidth: 560 }}>
        <fieldset disabled={isSavingMetadata} style={{ display: "grid", gap: "0.75rem" }}>
          <legend>Metadata</legend>
          <label>
            Title
            <input type="text" name="title" defaultValue={document.title ?? ""} style={{ width: "100%" }} />
          </label>
          <label>
            Collection
            <input type="text" name="collection" defaultValue={document.collection ?? ""} style={{ width: "100%" }} />
          </label>
          <label>
            Authors (comma separated)
            <input type="text" name="authors" defaultValue={formatAuthors(document.authors)} style={{ width: "100%" }} />
          </label>
          <label>
            Source type
            <input type="text" name="source_type" defaultValue={document.source_type ?? ""} style={{ width: "100%" }} />
          </label>
          <label>
            Abstract
            <textarea name="abstract" defaultValue={document.abstract ?? ""} rows={4} style={{ width: "100%" }} />
          </label>
          <button type="submit">{isSavingMetadata ? "Saving." : "Save changes"}</button>
        </fieldset>
        {metadataMessage && <p role="status">{metadataMessage}</p>}
        {metadataError && (
          <p role="alert" style={{ color: "crimson" }}>
            {metadataError}
          </p>
        )}
      </form>

      <div style={{ marginBottom: "1.5rem", display: "grid", gap: "0.35rem" }}>
        {document.source_url && (
          <a href={document.source_url} target="_blank" rel="noopener noreferrer">
            Original source
          </a>
        )}
        {document.collection && <p>Collection: {document.collection}</p>}
        {document.source_type && <p>Source type: {document.source_type}</p>}
        {document.authors && document.authors.length > 0 && <p>Authors: {formatAuthors(document.authors)}</p>}
        {document.channel && <p>Channel: {document.channel}</p>}
      </div>

      <section style={{ marginBottom: "2rem" }}>
        <h3>Annotations</h3>
        <form onSubmit={handleAnnotationSubmit} style={{ display: "grid", gap: "0.5rem", maxWidth: 520 }}>
          <textarea
            name="annotation"
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
            {document.annotations.map((annotation) => (
              <li key={annotation.id} style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: "0.5rem", padding: "0.75rem" }}>
                <p style={{ margin: "0 0 0.25rem" }}>{annotation.body}</p>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.85rem", color: "#555" }}>
                  <span>{formatTimestamp(annotation.updated_at)}</span>
                  <button type="button" onClick={() => handleDeleteAnnotation(annotation.id)} style={{ color: "crimson", background: "none", border: "none", cursor: "pointer" }}>
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
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
    </section>
  );
}
