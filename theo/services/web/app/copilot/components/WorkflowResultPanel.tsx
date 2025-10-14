import styles from "./WorkflowResultPanel.module.css";

import RAGAnswerBlock from "./RAGAnswer";
import type { CopilotResult, RAGCitation, WorkflowId } from "./types";
import { EXPORT_PRESET_LOOKUP } from "./export-presets";

type WorkflowResultPanelProps = {
  result: CopilotResult;
  onExport?: (citations: RAGCitation[]) => void;
  exporting?: boolean;
  status?: string | null;
  summary: string;
  workflowId: WorkflowId;
};

export default function WorkflowResultPanel({
  result,
  onExport,
  exporting,
  status,
  summary,
  workflowId,
}: WorkflowResultPanelProps): JSX.Element {
  const ragAnswerProps = {
    ...(onExport ? { onExport } : {}),
    ...(exporting !== undefined ? { exporting } : {}),
    ...(status !== undefined ? { status } : {}),
    workflowId,
  } as const;
  return (
    <section className={styles.panel}>
      <p className={styles.summary}>{summary}</p>
      {result.kind === "verse" && (
        <>
          <h3>Verse brief for {result.payload.osis}</h3>
          <RAGAnswerBlock
            answer={result.payload.answer}
            followUps={result.payload.follow_ups}
            {...ragAnswerProps}
          />
        </>
      )}
      {result.kind === "sermon" && (
        <>
          <h3>Sermon prep: {result.payload.topic}</h3>
          {result.payload.osis && <p>Anchored to {result.payload.osis}</p>}
          {result.payload.outline?.length ? (
            <>
              <h4>Outline</h4>
              <ul>
                {result.payload.outline.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </>
          ) : null}
          {result.payload.key_points?.length ? (
            <>
              <h4>Key points</h4>
              <ul>
                {result.payload.key_points.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </>
          ) : null}
          <RAGAnswerBlock
            answer={result.payload.answer}
            {...ragAnswerProps}
          />
        </>
      )}
      {result.kind === "comparative" && (
        <>
          <h3>Comparative analysis ({result.payload.osis})</h3>
          <p>Participants: {result.payload.participants.join(", ")}</p>
          <h4>Comparisons</h4>
          <ul>
            {result.payload.comparisons.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <RAGAnswerBlock
            answer={result.payload.answer}
            {...ragAnswerProps}
          />
        </>
      )}
      {result.kind === "multimedia" && (
        <>
          <h3>Multimedia digest</h3>
          {result.payload.collection && <p>Collection: {result.payload.collection}</p>}
          {result.payload.highlights.length > 0 && (
            <>
              <h4>Highlights</h4>
              <ul>
                {result.payload.highlights.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </>
          )}
          <RAGAnswerBlock
            answer={result.payload.answer}
            {...ragAnswerProps}
          />
        </>
      )}
      {result.kind === "devotional" && (
        <>
          <h3>Devotional guide for {result.payload.osis}</h3>
          <p>Focus: {result.payload.focus}</p>
          <h4>Reflection prompts</h4>
          <pre className={styles.codeBlock}>
            {result.payload.reflection}
          </pre>
          <h4>Prayer</h4>
          <pre className={styles.codeBlock}>
            {result.payload.prayer}
          </pre>
          <RAGAnswerBlock
            answer={result.payload.answer}
            {...ragAnswerProps}
          />
        </>
      )}
      {result.kind === "collaboration" && (
        <>
          <h3>Collaboration synthesis — {result.payload.thread}</h3>
          <pre className={styles.codeBlock}>
            {result.payload.synthesized_view}
          </pre>
          <RAGAnswerBlock
            answer={result.payload.answer}
            {...ragAnswerProps}
          />
        </>
      )}
      {result.kind === "curation" && (
        <>
          <h3>Corpus curation report</h3>
          <p>Effective since: {result.payload.since}</p>
          <p>Documents processed: {result.payload.documents_processed}</p>
          <h4>Summaries</h4>
          <ul>
            {result.payload.summaries.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      )}
      {result.kind === "export" && (() => {
        const preset = EXPORT_PRESET_LOOKUP[result.payload.preset];
        const label = preset?.label ?? result.payload.preset;
        return (
          <>
            <h3>Export preset: {label}</h3>
            <p>
              Format: {result.payload.format}
              {result.payload.filename ? ` · Filename: ${result.payload.filename}` : ""}
            </p>
            {result.payload.mediaType && <p>Media type: {result.payload.mediaType}</p>}
            <details>
              <summary>Preview content</summary>
              <pre className={styles.codeBlock}>
                {result.payload.content}
              </pre>
            </details>
          </>
        );
      })()}
    </section>
  );
}
