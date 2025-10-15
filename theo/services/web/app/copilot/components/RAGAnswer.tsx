import React from "react";
import styles from "./RAGAnswer.module.css";

import CitationList from "./CitationList";
import type { RAGAnswer, RAGCitation, WorkflowId } from "./types";

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
  workflowId?: WorkflowId;
};

export default function RAGAnswerBlock({
  answer,
  followUps,
  onExport,
  exporting,
  status,
  workflowId,
}: RAGAnswerProps): JSX.Element {
  const citationListProps = {
    citations: answer.citations,
    summaryText: answer.summary,
    ...(workflowId ? { workflowId } : {}),
    ...(onExport ? { onExport } : {}),
    ...(exporting !== undefined ? { exporting } : {}),
    ...(status !== undefined ? { status } : {}),
  } as const;
  const guardrailEntries = answer.guardrail_profile
    ? Object.entries(answer.guardrail_profile).filter(([, value]) => Boolean(value))
    : [];
  const showMetadata = Boolean(answer.model_name || answer.model_output || guardrailEntries.length);
  return (
    <div className={styles.container}>
      <section>
        <h4>Summary</h4>
        <p className={styles.summaryText}>{answer.summary}</p>
      </section>
      {showMetadata ? (
        <section>
          <h4>Model metadata</h4>
          <div className={styles.metadataContainer}>
            {answer.model_name ? (
              <div>
                <span className={styles.modelLabel}>Model:</span> {answer.model_name}
              </div>
            ) : null}
            {guardrailEntries.length ? (
              <dl className={styles.guardrailList}>
                {guardrailEntries.map(([key, value]) => (
                  <React.Fragment key={key}>
                    <dt className={styles.guardrailTerm}>{formatGuardrailLabel(key)}</dt>
                    <dd className={styles.guardrailDefinition}>{value}</dd>
                  </React.Fragment>
                ))}
              </dl>
            ) : null}
            {answer.model_output ? (
              <details>
                <summary>View raw model output</summary>
                <pre className={styles.rawOutput}>
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
