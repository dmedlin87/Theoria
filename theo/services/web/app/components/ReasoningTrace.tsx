"use client";

import type {
  ReasoningTrace,
  ReasoningTraceEvidence,
  ReasoningTraceStep,
  ReasoningTraceStatus,
} from "../lib/reasoning-trace";

type ReasoningTraceProps = {
  trace?: ReasoningTrace | null;
  className?: string;
  title?: string;
};

const STATUS_LABELS: Record<ReasoningTraceStatus, string> = {
  pending: "Pending evaluation",
  in_progress: "In progress",
  supported: "Supported",
  contradicted: "Contradicted",
  uncertain: "Uncertain",
  complete: "Complete",
};

const STATUS_CLASSES: Partial<Record<ReasoningTraceStatus, string>> = {
  supported: "chat-reasoning-trace__status--positive",
  contradicted: "chat-reasoning-trace__status--negative",
  in_progress: "chat-reasoning-trace__status--active",
  pending: "chat-reasoning-trace__status--pending",
  uncertain: "chat-reasoning-trace__status--uncertain",
  complete: "chat-reasoning-trace__status--complete",
};

function classNames(
  ...classes: Array<string | false | null | undefined>
): string {
  return classes.filter(Boolean).join(" ");
}

export function ReasoningTrace({
  trace,
  className,
  title = "Reasoning trace",
}: ReasoningTraceProps): JSX.Element | null {
  if (!trace || !Array.isArray(trace.steps) || trace.steps.length === 0) {
    return null;
  }

  const containerClass = classNames("chat-reasoning-trace", className);
  const summary = typeof trace.summary === "string" ? trace.summary.trim() : "";
  const strategy = typeof trace.strategy === "string" ? trace.strategy.trim() : "";

  return (
    <section className={containerClass} aria-label={title} role="group">
      <header className="chat-reasoning-trace__header">
        <h4 className="chat-reasoning-trace__title">{title}</h4>
        {strategy ? <span className="chat-reasoning-trace__strategy">{strategy}</span> : null}
      </header>
      {summary ? <p className="chat-reasoning-trace__summary">{summary}</p> : null}
      <ol className="chat-reasoning-trace__steps">
        {trace.steps.map((step, index) => (
          <ReasoningTraceItem key={step.id || index} step={step} index={index} level={1} />
        ))}
      </ol>
    </section>
  );
}

function ReasoningTraceItem({
  step,
  index,
  level,
}: {
  step: ReasoningTraceStep;
  index: number;
  level: number;
}) {
  const label = typeof step.label === "string" && step.label.trim()
    ? step.label.trim()
    : `Step ${index + 1}`;
  const detail = typeof step.detail === "string" ? step.detail.trim() : "";
  const outcome = typeof step.outcome === "string" ? step.outcome.trim() : "";
  const confidence = typeof step.confidence === "number" && Number.isFinite(step.confidence)
    ? Math.min(Math.max(step.confidence, 0), 1)
    : null;
  const status = normaliseStatus(step.status);
  const citations = Array.isArray(step.citations)
    ? step.citations
        .map((value) =>
          typeof value === "number" && Number.isFinite(value) ? Math.max(0, Math.trunc(value)) : null,
        )
        .filter((value): value is number => value !== null)
    : [];
  const evidence = Array.isArray(step.evidence)
    ? step.evidence.filter((item): item is ReasoningTraceEvidence =>
        Boolean(item && typeof item === "object" && typeof item.text === "string" && item.text.trim()),
      )
    : [];
  const children = Array.isArray(step.children)
    ? step.children.filter((child): child is ReasoningTraceStep => Boolean(child && typeof child === "object"))
    : [];

  return (
    <li
      className={classNames(
        "chat-reasoning-trace__step",
        status ? `chat-reasoning-trace__step--${status}` : null,
      )}
      data-level={level}
    >
      <div className="chat-reasoning-trace__stepHeader">
        <span className="chat-reasoning-trace__stepIndex" aria-hidden="true">
          {index + 1}
        </span>
        <div className="chat-reasoning-trace__stepMeta">
          <span className="chat-reasoning-trace__stepLabel">{label}</span>
          {status ? (
            <span className={classNames("chat-reasoning-trace__status", STATUS_CLASSES[status])}>
              {STATUS_LABELS[status]}
            </span>
          ) : null}
        </div>
      </div>
      {detail ? <p className="chat-reasoning-trace__detail">{detail}</p> : null}
      {outcome ? (
        <p className="chat-reasoning-trace__outcome">
          <span className="chat-reasoning-trace__label">Outcome:</span> {outcome}
        </p>
      ) : null}
      {confidence !== null ? (
        <p className="chat-reasoning-trace__confidence">
          <span className="chat-reasoning-trace__label">Confidence:</span> {Math.round(confidence * 100)}%
        </p>
      ) : null}
      {citations.length > 0 ? (
        <p className="chat-reasoning-trace__citations">
          <span className="chat-reasoning-trace__label">Citations:</span> {formatCitationList(citations)}
        </p>
      ) : null}
      {evidence.length > 0 ? (
        <ol className="chat-reasoning-trace__evidence" aria-label="Supporting evidence">
          {evidence.map((item, evidenceIndex) => (
            <li key={item.id || `${step.id}-evidence-${evidenceIndex}`} className="chat-reasoning-trace__evidenceItem">
              {item.label ? (
                <span className="chat-reasoning-trace__evidenceLabel">{item.label}: </span>
              ) : null}
              <span>{item.text.trim()}</span>
              {Array.isArray(item.citationIds) && item.citationIds.length > 0 ? (
                <span className="chat-reasoning-trace__evidenceCitations">
                  ({formatCitationList(
                    item.citationIds
                      .map((value) =>
                        typeof value === "number" && Number.isFinite(value)
                          ? Math.max(0, Math.trunc(value))
                          : null,
                      )
                      .filter((value): value is number => value !== null),
                  )})
                </span>
              ) : null}
            </li>
          ))}
        </ol>
      ) : null}
      {children.length > 0 ? (
        <ol className="chat-reasoning-trace__steps chat-reasoning-trace__steps--nested">
          {children.map((child, childIndex) => (
            <ReasoningTraceItem key={child.id || `${step.id}-${childIndex}`} step={child} index={childIndex} level={level + 1} />
          ))}
        </ol>
      ) : null}
    </li>
  );
}

function normaliseStatus(status: ReasoningTraceStep["status"]): ReasoningTraceStatus | null {
  if (!status) {
    return null;
  }
  const value = typeof status === "string" ? status.trim().toLowerCase() : "";
  if (
    value === "pending" ||
    value === "in_progress" ||
    value === "supported" ||
    value === "contradicted" ||
    value === "uncertain" ||
    value === "complete"
  ) {
    return value;
  }
  return null;
}

function formatCitationList(values: number[]): string {
  return values
    .map((value) => value + 1)
    .filter((value, position, array) => array.indexOf(value) === position)
    .sort((a, b) => a - b)
    .join(", ");
}

export default ReasoningTrace;
