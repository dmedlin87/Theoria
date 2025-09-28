import React from "react";

import CitationList from "./CitationList";
import type { RAGAnswer, RAGCitation } from "./types";

function formatGuardrailLabel(key: string): string {
  return key
    .split("_")
    .filter(Boolean)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ");
}

type RAGAnswerProps = {
  answer: RAGAnswer;
  followUps?: string[];
  onExport?: (citations: RAGCitation[]) => void;
  exporting?: boolean;
  status?: string | null;
};

export default function RAGAnswerBlock({
  answer,
  followUps,
  onExport,
  exporting,
  status,
}: RAGAnswerProps): JSX.Element {
  const citationListProps = {
    citations: answer.citations,
    ...(onExport ? { onExport } : {}),
    ...(exporting !== undefined ? { exporting } : {}),
    ...(status !== undefined ? { status } : {}),
  } as const;
  const guardrailEntries = answer.guardrail_profile
    ? Object.entries(answer.guardrail_profile).filter(([, value]) => Boolean(value))
    : [];
  const showMetadata = Boolean(answer.model_name || answer.model_output || guardrailEntries.length);
  return (
    <div style={{ marginTop: "1rem", display: "grid", gap: "1rem" }}>
      <section>
        <h4>Summary</h4>
        <p style={{ lineHeight: 1.6 }}>{answer.summary}</p>
      </section>
      {showMetadata ? (
        <section>
          <h4>Model metadata</h4>
          <div style={{ display: "grid", gap: "0.25rem" }}>
            {answer.model_name ? (
              <div>
                <span style={{ fontWeight: 600 }}>Model:</span> {answer.model_name}
              </div>
            ) : null}
            {guardrailEntries.length ? (
              <dl
                style={{
                  margin: 0,
                  display: "grid",
                  gridTemplateColumns: "max-content 1fr",
                  columnGap: "0.5rem",
                  rowGap: "0.25rem",
                }}
              >
                {guardrailEntries.map(([key, value]) => (
                  <React.Fragment key={key}>
                    <dt style={{ fontWeight: 600 }}>{formatGuardrailLabel(key)}</dt>
                    <dd style={{ margin: 0 }}>{value}</dd>
                  </React.Fragment>
                ))}
              </dl>
            ) : null}
            {answer.model_output ? (
              <details>
                <summary>View raw model output</summary>
                <pre
                  style={{
                    marginTop: "0.5rem",
                    background: "#f9fafb",
                    padding: "0.75rem",
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {answer.model_output}
                </pre>
              </details>
            ) : null}
          </div>
        </section>
      ) : null}
      <CitationList {...citationListProps} />
      {followUps?.length ? (
        <div>
          <h4>Suggested follow-ups</h4>
          <ul>
            {followUps.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
