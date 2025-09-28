import Link from "next/link";

import type { RAGCitation } from "./types";

type CitationListProps = {
  citations: RAGCitation[];
  onExport?: (citations: RAGCitation[]) => void;
  exporting?: boolean;
  status?: string | null;
};

export default function CitationList({
  citations,
  onExport,
  exporting,
  status,
}: CitationListProps): JSX.Element | null {
  if (!citations.length) {
    return null;
  }
  const hasMissingPassage = citations.some(
    (citation) => !citation.passage_id || !citation.passage_id.trim(),
  );
  return (
    <div style={{ marginTop: "1rem" }}>
      <h4>Citations</h4>
      <ol style={{ paddingLeft: "1.25rem" }}>
        {citations.map((citation) => {
          const content = (
            <>
              <span style={{ fontWeight: 600 }}>
                {citation.osis} ({citation.anchor})
              </span>
              {citation.document_title && (
                <span
                  style={{ display: "block", marginTop: "0.25rem", fontSize: "0.9rem", color: "#475569" }}
                >
                  {citation.document_title}
                </span>
              )}
              <span
                style={{
                  display: "block",
                  marginTop: "0.35rem",
                  fontStyle: "italic",
                  color: "#0f172a",
                  lineHeight: 1.4,
                }}
              >
                “{citation.snippet}”
              </span>
            </>
          );
          const commonStyle = {
            display: "block",
            padding: "0.75rem",
            border: "1px solid #e2e8f0",
            borderRadius: "0.5rem",
            background: "#f8fafc",
            textDecoration: "none",
            color: "inherit",
          } as const;
          return (
            <li key={citation.index} style={{ marginBottom: "0.5rem" }}>
              {citation.source_url ? (
                <Link
                  href={citation.source_url}
                  prefetch={false}
                  style={commonStyle}
                  title={`${citation.document_title ?? "Document"} — ${citation.snippet}`}
                >
                  {content}
                </Link>
              ) : (
                <div style={commonStyle}>{content}</div>
              )}
            </li>
          );
        })}
      </ol>
      {onExport && (
        <div style={{ marginTop: "0.75rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <button
            type="button"
            onClick={() => onExport(citations)}
            disabled={exporting || hasMissingPassage}
          >
            {exporting ? "Exporting citations…" : "Export selected citations"}
          </button>
          {hasMissingPassage ? (
            <p style={{ margin: 0, color: "#b91c1c" }}>
              Each citation needs a passage reference before you can export.
            </p>
          ) : null}
          {status ? <p style={{ margin: 0, color: "#047857" }}>{status}</p> : null}
        </div>
      )}
    </div>
  );
}
