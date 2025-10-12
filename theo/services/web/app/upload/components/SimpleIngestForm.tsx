"use client";

import { FormEvent, useRef, useState } from "react";

const DEFAULT_COLLECTION = "uploads";
const DEFAULT_AUTHOR = "Theoria";

export type SimpleIngestEvent = {
  event: string;
  [key: string]: unknown;
};

interface SimpleIngestFormProps {
  onSubmit: (payload: {
    sources: string[];
    mode: "api" | "worker";
    batch_size: number;
    dry_run: boolean;
    post_batch?: string[];
    metadata?: Record<string, unknown>;
  }) => Promise<void>;
  isRunning: boolean;
  error: string | null;
  success: string | null;
  progress: SimpleIngestEvent[];
}

function describeSimpleEvent(event: SimpleIngestEvent): string {
  switch (event.event) {
    case "start": {
      const total = event.total as number | undefined;
      const mode = (event.mode as string | undefined) ?? "api";
      return `Started ingest (${total ?? 0} item${total === 1 ? "" : "s"}) in ${mode} mode.`;
    }
    case "discovered": {
      const target = (event.target as string | undefined) ?? "source";
      const type = (event.source_type as string | undefined) ?? "unknown";
      return `Discovered [${type}] ${target}.`;
    }
    case "batch": {
      const number = event.number as number | undefined;
      const size = event.size as number | undefined;
      return `Batch ${number ?? 0}: ${size ?? 0} item${size === 1 ? "" : "s"}.`;
    }
    case "dry-run": {
      const target = (event.target as string | undefined) ?? "source";
      return `Dry-run preview: ${target}.`;
    }
    case "processed": {
      const target = (event.target as string | undefined) ?? "source";
      const docId = (event.document_id as string | undefined) ?? "document";
      return `Processed ${target} → document ${docId}.`;
    }
    case "queued": {
      const target = (event.target as string | undefined) ?? "source";
      const taskId = (event.task_id as string | undefined) ?? "queued";
      return `Queued ${target} → task ${taskId}.`;
    }
    case "warning": {
      return String(event.message ?? "Warning emitted during ingest.");
    }
    case "empty": {
      return "No supported sources discovered.";
    }
    case "complete": {
      const processed = (event.processed as number | undefined) ?? 0;
      const queued = (event.queued as number | undefined) ?? 0;
      return `Completed ingest (processed ${processed}, queued ${queued}).`;
    }
    case "error": {
      return `Error: ${String(event.message ?? "ingest failed")}`;
    }
    default:
      return event.event;
  }
}

export default function SimpleIngestForm({
  onSubmit,
  isRunning,
  error,
  success,
  progress,
}: SimpleIngestFormProps): JSX.Element {
  const [sources, setSources] = useState("");
  const [mode, setMode] = useState<"api" | "worker">("api");
  const [batchSize, setBatchSize] = useState(10);
  const [collection, setCollection] = useState(DEFAULT_COLLECTION);
  const [author, setAuthor] = useState(DEFAULT_AUTHOR);
  const [metadata, setMetadata] = useState("");
  const [dryRun, setDryRun] = useState(false);
  const [postBatch, setPostBatch] = useState<string[]>([]);
  const formRef = useRef<HTMLFormElement | null>(null);

  const togglePostBatchStep = (step: string) => {
    setPostBatch((current) => {
      if (current.includes(step)) {
        return current.filter((value) => value !== step);
      }
      return [...current, step];
    });
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const normalizedSources = sources
      .split(/\r?\n/)
      .flatMap((line) => line.split(","))
      .map((value) => value.trim())
      .filter((value) => value.length > 0);

    const parsedMetadata: Record<string, unknown> = {};
    if (collection.trim()) {
      parsedMetadata.collection = collection.trim();
    }
    if (author.trim()) {
      parsedMetadata.author = author.trim();
    }
    if (metadata.trim()) {
      try {
        const parsed = JSON.parse(metadata);
        if (parsed && typeof parsed === "object") {
          Object.assign(parsedMetadata, parsed as Record<string, unknown>);
        }
      } catch {
        return;
      }
    }

    const payload: {
      sources: string[];
      mode: "api" | "worker";
      batch_size: number;
      dry_run: boolean;
      post_batch?: string[];
      metadata?: Record<string, unknown>;
    } = {
      sources: normalizedSources,
      mode,
      batch_size: batchSize,
      dry_run: dryRun,
    };

    if (postBatch.length > 0) {
      payload.post_batch = postBatch;
    }
    if (Object.keys(parsedMetadata).length > 0) {
      payload.metadata = parsedMetadata;
    }

    await onSubmit(payload);

    if (!dryRun && success) {
      setSources("");
    }
  };

  return (
    <div className="simple-ingest-section">
      <form ref={formRef} onSubmit={handleSubmit} aria-label="Simple ingest" className="mb-4">
        <fieldset disabled={isRunning} className="simple-ingest-fieldset">
          <legend className="simple-ingest-legend">Quick ingest</legend>

          <div className="form-field">
            <label htmlFor="sources" className="form-label">
              Sources (one per line or comma-separated)
            </label>
            <textarea
              id="sources"
              name="sources"
              rows={4}
              placeholder={"/srv/imports/sermons\nhttps://example.com/homily"}
              value={sources}
              onChange={(event) => setSources(event.target.value)}
              className="form-textarea"
              required
            />
            <p className="form-hint">
              The CLI defaults will tag new documents with the "{DEFAULT_COLLECTION}" collection and "
              {DEFAULT_AUTHOR}" author unless you override them below.
            </p>
          </div>

          <details className="simple-ingest-details">
            <summary className="simple-ingest-summary">Advanced settings</summary>
            <div className="stack-md mt-2">
              <div className="form-field">
                <label htmlFor="mode" className="form-label">
                  Mode
                </label>
                <select
                  id="mode"
                  name="mode"
                  value={mode}
                  onChange={(event) => setMode(event.target.value === "worker" ? "worker" : "api")}
                  className="form-select"
                >
                  <option value="api">API (synchronous)</option>
                  <option value="worker">Worker queue</option>
                </select>
              </div>

              <div className="form-field">
                <label htmlFor="batch-size" className="form-label">
                  Batch size
                </label>
                <input
                  id="batch-size"
                  type="number"
                  min={1}
                  value={batchSize}
                  onChange={(event) => {
                    const next = Number(event.target.value);
                    setBatchSize(Number.isFinite(next) && next > 0 ? next : 1);
                  }}
                  className="form-input"
                />
              </div>

              <div className="form-field">
                <label htmlFor="collection" className="form-label">
                  Collection override
                </label>
                <input
                  id="collection"
                  type="text"
                  value={collection}
                  onChange={(event) => setCollection(event.target.value)}
                  className="form-input"
                />
              </div>

              <div className="form-field">
                <label htmlFor="author" className="form-label">
                  Author override
                </label>
                <input
                  id="author"
                  type="text"
                  value={author}
                  onChange={(event) => setAuthor(event.target.value)}
                  className="form-input"
                />
              </div>

              <div className="form-field">
                <label htmlFor="extra-metadata" className="form-label">
                  Additional metadata (JSON)
                </label>
                <textarea
                  id="extra-metadata"
                  name="extra_metadata"
                  rows={4}
                  value={metadata}
                  onChange={(event) => setMetadata(event.target.value)}
                  placeholder='{"tags":["Advent"],"year":2024}'
                  className="form-textarea"
                />
              </div>

              <fieldset className="post-batch-fieldset">
                <legend className="form-label">Post-batch options</legend>
                <div className="stack-sm">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={postBatch.includes("summaries")}
                      onChange={() => togglePostBatchStep("summaries")}
                    />
                    <span>Generate summaries</span>
                  </label>
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={postBatch.includes("tags")}
                      onChange={() => togglePostBatchStep("tags")}
                    />
                    <span>Run metadata enrichment</span>
                  </label>
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={postBatch.includes("biblio")}
                      onChange={() => togglePostBatchStep("biblio")}
                    />
                    <span>Queue bibliography refresh</span>
                  </label>
                </div>
              </fieldset>

              <label className="checkbox-label">
                <input type="checkbox" checked={dryRun} onChange={(event) => setDryRun(event.target.checked)} />
                <span>Dry run (list batches without ingesting)</span>
              </label>
            </div>
          </details>

          <button type="submit" className="btn btn-primary mt-3">
            {isRunning ? <><span className="spinner" /> Running ingest…</> : "Start ingest"}
          </button>
        </fieldset>
      </form>

      {error && (
        <div className="alert alert-danger mb-3">
          <div className="alert__message">{error}</div>
        </div>
      )}

      {success && !error && (
        <div className="alert alert-success mb-3" role="status">
          <div className="alert__message">{success}</div>
        </div>
      )}

      {progress.length > 0 && (
        <div className="simple-ingest-progress">
          <h3 className="text-lg font-semibold mb-2">Ingest progress</h3>
          <ol className="progress-list">
            {progress.map((event, index) => (
              <li key={`${event.event}-${index}`}>{describeSimpleEvent(event)}</li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
