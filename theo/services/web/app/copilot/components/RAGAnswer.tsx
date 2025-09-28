import CitationList from "./CitationList";
import type { RAGAnswer, RAGCitation } from "./types";

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
  return (
    <div style={{ marginTop: "1rem", display: "grid", gap: "1rem" }}>
      <section>
        <h4>Summary</h4>
        <p style={{ lineHeight: 1.6 }}>{answer.summary}</p>
      </section>
      <CitationList citations={answer.citations} onExport={onExport} exporting={exporting} status={status} />
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
