"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { getApiBaseUrl } from "../../lib/api";
import styles from "./CitationList.module.css";
import type { components } from "../../lib/generated/api";
import type { RAGCitation, WorkflowId } from "./types";

type DocumentAnnotation = components["schemas"]["DocumentAnnotationResponse"];

type CitationListProps = {
  citations: RAGCitation[];
  summaryText?: string | null;
  workflowId?: WorkflowId;
  onExport?: (citations: RAGCitation[]) => void;
  exporting?: boolean;
  status?: string | null;
};

function normaliseAnnotations(
  payload: DocumentAnnotation[] | undefined,
): DocumentAnnotation[] {
  if (!Array.isArray(payload)) {
    return [];
  }
  return payload.map((annotation) => ({
    ...annotation,
    passage_ids: Array.isArray(annotation.passage_ids)
      ? annotation.passage_ids
      : [],
  }));
}

function safeRandomId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    try {
      return crypto.randomUUID();
    } catch {
      // ignore and fall through to fallback id
    }
  }
  return `bundle-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export default function CitationList({
  citations,
  summaryText,
  workflowId,
  onExport,
  exporting,
  status,
}: CitationListProps): JSX.Element | null {
  const baseUrl = useMemo(() => getApiBaseUrl().replace(/\/$/, ""), []);
  const hasSummary = useMemo(() => Boolean((summaryText ?? "").trim()), [summaryText]);
  const documentChoices = useMemo(() => {
    const seen = new Map<string, string | null>();
    for (const citation of citations) {
      if (citation.document_id) {
        seen.set(citation.document_id, citation.document_title ?? null);
      }
    }
    return Array.from(seen.entries()).map(([id, title]) => ({ id, title }));
  }, [citations]);
  const documentChoiceIds = useMemo(
    () => documentChoices.map((item) => item.id),
    [documentChoices],
  );
  const documentChoiceKey = useMemo(() => {
    return documentChoiceIds.slice().sort().join("|");
  }, [documentChoiceIds]);

  const documentChoiceIdsRef = useRef(documentChoiceIds);
  useEffect(() => {
    documentChoiceIdsRef.current = documentChoiceIds;
  }, [documentChoiceIds]);

  const [selectedDocumentId, setSelectedDocumentId] = useState<string>(
    documentChoices[0]?.id ?? "",
  );
  useEffect(() => {
    const firstChoice = documentChoices[0];
    if (!firstChoice) {
      setSelectedDocumentId("");
      return;
    }
    setSelectedDocumentId((current) => {
      if (current && documentChoices.some((choice) => choice.id === current)) {
        return current;
      }
      return firstChoice.id;
    });
  }, [documentChoices]);

  const [annotationsByDocument, setAnnotationsByDocument] = useState<
    Record<string, DocumentAnnotation[]>
  >({});
  const [annotationsError, setAnnotationsError] = useState<string | null>(null);
  const [isLoadingAnnotations, setIsLoadingAnnotations] = useState(false);

  useEffect(() => {
    const docIds = documentChoiceIdsRef.current;
    if (!docIds.length) {
      setAnnotationsByDocument({});
      setAnnotationsError(null);
      setIsLoadingAnnotations(false);
      return;
    }
    let cancelled = false;
    const controller = new AbortController();
    const fetchAnnotations = async () => {
      setIsLoadingAnnotations(true);
      setAnnotationsError(null);
      try {
        const results: Record<string, DocumentAnnotation[]> = {};
        await Promise.all(
          docIds.map(async (docId) => {
            const response = await fetch(
              `${baseUrl}/documents/${docId}/annotations`,
              { signal: controller.signal },
            );
            if (!response.ok) {
              throw new Error(await response.text());
            }
            const data = (await response.json()) as DocumentAnnotation[];
            results[docId] = normaliseAnnotations(data);
          }),
        );
        if (!cancelled) {
          setAnnotationsByDocument(results);
        }
      } catch (error) {
        if (!cancelled) {
          const message =
            error instanceof Error && error.message
              ? error.message
              : "Unable to load linked notes";
          setAnnotationsError(message);
        }
      } finally {
        if (!cancelled) {
          setIsLoadingAnnotations(false);
        }
      }
    };
    void fetchAnnotations();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [baseUrl, documentChoiceKey]);

  const [isSavingBundle, setIsSavingBundle] = useState(false);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const selectedDocCitations = useMemo(
    () =>
      citations.filter(
        (citation) => citation.document_id === selectedDocumentId,
      ),
    [citations, selectedDocumentId],
  );
  const missingPassage = selectedDocCitations.some(
    (citation) => !citation.passage_id || !citation.passage_id.trim(),
  );

  const handleSaveClaimEvidence = async () => {
    const summary = (summaryText ?? "").trim();
    if (!selectedDocumentId) {
      setSaveError("Select a cited document to save notes.");
      return;
    }
    if (!summary) {
      setSaveError("A summary is required to create a claim note.");
      return;
    }
    if (!selectedDocCitations.length) {
      setSaveError("The selected document has no citations in this answer.");
      return;
    }
    if (missingPassage) {
      setSaveError("Each citation needs a passage reference before saving notes.");
      return;
    }
    const passageIds = Array.from(
      new Set(
        selectedDocCitations
          .map((citation) => citation.passage_id)
          .filter((value): value is string => Boolean(value && value.trim())),
      ),
    );
    if (!passageIds.length) {
      setSaveError("Unable to identify passage references for these citations.");
      return;
    }

    const bundleId = safeRandomId();
    const metadataBase: Record<string, unknown> = {
      source: "copilot",
      workflow: workflowId ?? null,
      citation_indices: selectedDocCitations.map((item) => item.index),
      citation_anchors: selectedDocCitations.map((item) => ({
        index: item.index,
        osis: item.osis,
        anchor: item.anchor,
      })),
    };

    const evidenceText = selectedDocCitations
      .map((citation) => `${citation.osis} (${citation.anchor}): ${citation.snippet}`)
      .join("\n\n");

    setIsSavingBundle(true);
    setSaveError(null);
    setSaveStatus(null);

    try {
      const claimResponse = await fetch(
        `${baseUrl}/documents/${selectedDocumentId}/annotations`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            type: "claim",
            text: summary,
            group_id: bundleId,
            passage_ids: passageIds,
            metadata: { ...metadataBase, bundle_id: bundleId },
          }),
        },
      );
      if (!claimResponse.ok) {
        throw new Error(await claimResponse.text());
      }
      const claim = (await claimResponse.json()) as DocumentAnnotation;

      const evidenceResponse = await fetch(
        `${baseUrl}/documents/${selectedDocumentId}/annotations`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            type: "evidence",
            text: evidenceText,
            group_id: bundleId,
            passage_ids: passageIds,
            metadata: { ...metadataBase, linked_claim_id: claim.id },
          }),
        },
      );
      if (!evidenceResponse.ok) {
        throw new Error(await evidenceResponse.text());
      }
      const evidence = (await evidenceResponse.json()) as DocumentAnnotation;

      setAnnotationsByDocument((prev) => {
        const current = prev[selectedDocumentId] ?? [];
        return {
          ...prev,
          [selectedDocumentId]: [...current, claim, evidence],
        };
      });
      const docTitle = documentChoices.find(
        (choice) => choice.id === selectedDocumentId,
      )?.title;
      setSaveStatus(
        docTitle
          ? `Saved claim & evidence to “${docTitle}”.`
          : "Saved claim & evidence.",
      );
    } catch (error) {
      const message =
        error instanceof Error && error.message
          ? error.message
          : "Unable to save claim and evidence";
      setSaveError(message);
    } finally {
      setIsSavingBundle(false);
    }
  };

  if (citations.length === 0) {
    return null;
  }

  return (
    <div className={styles.container}>
      <div>
        <h4>Citations</h4>
        <ol className={styles.citationsList}>
          {citations.map((citation) => {
            const notes = (annotationsByDocument[citation.document_id] ?? []).filter(
              (annotation) =>
                Boolean(citation.passage_id) &&
                Array.isArray(annotation.passage_ids) &&
                annotation.passage_ids.includes(citation.passage_id),
            );
            const content = (
              <>
                <span className={styles.citationReference}>
                  {citation.osis} ({citation.anchor})
                </span>
                {citation.document_title && (
                  <span className={styles.documentTitle}>
                    {citation.document_title}
                  </span>
                )}
                <span className={styles.citationSnippet}>
                  "{citation.snippet}"
                </span>
                {notes.length ? (
                  <ul className={styles.notesList}>
                    {notes.map((annotation) => (
                      <li
                        key={`${annotation.id}-${citation.index}`}
                        className={styles.noteItem}
                      >
                        <span className={styles.noteHeader}>
                          {annotation.type.charAt(0).toUpperCase() + annotation.type.slice(1)}
                          {annotation.stance ? ` · ${annotation.stance}` : ""}
                        </span>
                        <span className={styles.noteBody}>
                          {annotation.body}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </>
            );
            return (
              <li key={citation.index} className={styles.citationItem}>
                {citation.source_url ? (
                  <Link
                    href={citation.source_url}
                    prefetch={false}
                    className={styles.citationCard}
                    title={`${citation.document_title ?? "Document"} — ${citation.snippet}`}
                  >
                    {content}
                  </Link>
                ) : (
                  <div className={styles.citationCard}>{content}</div>
                )}
              </li>
            );
          })}
        </ol>
      </div>

      {documentChoices.length > 0 && hasSummary ? (
        <section className={styles.researchNoteSection}>
          <div className={styles.formRow}>
            <label className={styles.formLabel}>
              <span className={styles.labelText}>Add as research note</span>
              <select
                value={selectedDocumentId}
                onChange={(event) => setSelectedDocumentId(event.target.value)}
                className={styles.selectInput}
              >
                {documentChoices.map((choice) => (
                  <option key={choice.id} value={choice.id}>
                    {choice.title ?? choice.id}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={handleSaveClaimEvidence}
              disabled={isSavingBundle || missingPassage}
              className={styles.saveButton}
            >
              {isSavingBundle ? "Saving notes…" : "Save claim & evidence"}
            </button>
          </div>
          {missingPassage ? (
            <p className={styles.errorMessage}>
              Each citation needs a passage reference before saving notes.
            </p>
          ) : null}
          {saveError ? (
            <p role="alert" className={styles.errorMessage}>
              {saveError}
            </p>
          ) : null}
          {saveStatus ? (
            <p className={styles.successMessage}>{saveStatus}</p>
          ) : null}
        </section>
      ) : null}

      {onExport && (
        <div className={styles.exportSection}>
          <button
            type="button"
            onClick={() => onExport(citations)}
            disabled={exporting || citations.some((citation) => !citation.passage_id)}
          >
            {exporting ? "Exporting citations…" : "Export selected citations"}
          </button>
          {citations.some((citation) => !citation.passage_id) ? (
            <p className={styles.errorMessage}>
              Each citation needs a passage reference before you can export.
            </p>
          ) : null}
          {status ? <p className={styles.successMessage}>{status}</p> : null}
        </div>
      )}

      {isLoadingAnnotations ? (
        <p className={styles.loadingMessage}>Loading linked notes…</p>
      ) : null}
      {annotationsError ? (
        <p role="alert" className={styles.errorMessage}>
          {annotationsError}
        </p>
      ) : null}
    </div>
  );
}
