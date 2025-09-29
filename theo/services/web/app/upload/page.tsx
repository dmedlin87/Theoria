"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import ErrorCallout from "../components/ErrorCallout";
import { getApiBaseUrl } from "../lib/api";
import { type ErrorDetails, parseErrorResponse } from "../lib/errorUtils";

const DEFAULT_COLLECTION = "uploads";
const DEFAULT_AUTHOR = "Theo Engine";

type UploadStatus = {
  kind: "success" | "error" | "info";
  message: string;
  traceId: string | null;
  source?: "file" | "url";
};

type JobStatus = {
  id: string;
  document_id?: string | null;
  job_type: string;
  status: string;
  task_id?: string | null;
  error?: string | null;
  created_at: string;
  updated_at: string;
};

type SimpleIngestEvent = {
  event: string;
  [key: string]: unknown;
};

async function readErrorDetails(response: Response, fallback: string): Promise<ErrorDetails> {
  return parseErrorResponse(response, fallback);
}

async function uploadFile({
  file,
  frontmatter,
}: {
  file: File;
  frontmatter: string;
}): Promise<UploadStatus> {
  const formData = new FormData();
  formData.append("file", file);
  if (frontmatter.trim()) {
    formData.append("frontmatter", frontmatter.trim());
  }

  const response = await fetch(`/api/ingest/file`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const { message, traceId } = await readErrorDetails(response, "Upload failed");
    return { kind: "error", message, traceId, source: "file" } satisfies UploadStatus;
  }

  const payload = (await response.json()) as { document_id: string; status: string };
  return {
    kind: "success",
    message: `Upload complete. Document ID: ${payload.document_id}`,
    traceId: null,
    source: "file",
  } satisfies UploadStatus;
}

async function uploadUrl({
  url,
  sourceType,
  frontmatter,
}: {
  url: string;
  sourceType: string;
  frontmatter: string;
}): Promise<UploadStatus> {
  let parsedFrontmatter: unknown = undefined;
  if (frontmatter.trim()) {
    try {
      parsedFrontmatter = JSON.parse(frontmatter);
    } catch (error) {
      return {
        kind: "error",
        message: "Frontmatter must be valid JSON",
        traceId: null,
        source: "url",
      } satisfies UploadStatus;
    }
  }

  const payload: Record<string, unknown> = { url };
  if (sourceType) {
    payload.source_type = sourceType;
  }
  if (parsedFrontmatter) {
    payload.frontmatter = parsedFrontmatter;
  }

  const response = await fetch(`/api/ingest/url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const { message, traceId } = await readErrorDetails(response, "URL ingestion failed");
    return { kind: "error", message, traceId, source: "url" } satisfies UploadStatus;
  }

  const data = (await response.json()) as { document_id: string; status: string };
  return {
    kind: "success",
    message: `URL queued. Document ID: ${data.document_id}`,
    traceId: null,
    source: "url",
  } satisfies UploadStatus;
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString();
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

export default function UploadPage(): JSX.Element {
  const [simpleSources, setSimpleSources] = useState("");
  const [simpleMode, setSimpleMode] = useState<"api" | "worker">("api");
  const [simpleBatchSize, setSimpleBatchSize] = useState(10);
  const [simpleCollection, setSimpleCollection] = useState(DEFAULT_COLLECTION);
  const [simpleAuthor, setSimpleAuthor] = useState(DEFAULT_AUTHOR);
  const [simpleMetadata, setSimpleMetadata] = useState("");
  const [simpleDryRun, setSimpleDryRun] = useState(false);
  const [simplePostBatch, setSimplePostBatch] = useState<string[]>([]);
  const [simpleProgress, setSimpleProgress] = useState<SimpleIngestEvent[]>([]);
  const [simpleError, setSimpleError] = useState<string | null>(null);
  const [simpleSuccess, setSimpleSuccess] = useState<string | null>(null);
  const [isRunningSimple, setIsRunningSimple] = useState(false);
  const simpleFormRef = useRef<HTMLFormElement | null>(null);

  const [status, setStatus] = useState<UploadStatus | null>(null);
  const [isUploadingFile, setIsUploadingFile] = useState(false);
  const [isSubmittingUrl, setIsSubmittingUrl] = useState(false);
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [jobError, setJobError] = useState<ErrorDetails | null>(null);
  const fileFormRef = useRef<HTMLFormElement | null>(null);
  const urlFormRef = useRef<HTMLFormElement | null>(null);
  const fetchJobsRef = useRef<(() => Promise<void>) | undefined>(undefined);

  const baseUrl = useMemo(() => getApiBaseUrl().replace(/\/$/, ""), []);

  useEffect(() => {
    let isMounted = true;

    const fetchJobs = async () => {
      try {
        const response = await fetch(`${baseUrl}/jobs?limit=25`, { cache: "no-store" });
        if (!response.ok) {
          const details = await readErrorDetails(response, "Unable to load jobs");
          if (isMounted) {
            setJobError(details);
          }
          return;
        }
        const payload = (await response.json()) as { jobs: JobStatus[] };
        if (isMounted) {
          setJobs(payload.jobs ?? []);
          setJobError(null);
        }
      } catch (error) {
        if (isMounted) {
          const fallbackMessage =
            error instanceof Error && error.message ? error.message : "Unable to load jobs";
          const message =
            error instanceof TypeError && /fetch/i.test(error.message)
              ? "Unable to reach the ingestion service. Please verify the API is running."
              : fallbackMessage;
          const traceId =
            typeof error === "object" && error && "traceId" in error
              ? ((error as { traceId?: string | null }).traceId ?? null)
              : null;
          setJobError({ message, traceId });
        }
      }
    };

    fetchJobsRef.current = fetchJobs;
    void fetchJobs();
    const interval = window.setInterval(fetchJobs, 5000);
    return () => {
      isMounted = false;
      window.clearInterval(interval);
      fetchJobsRef.current = undefined;
    };
  }, [baseUrl]);

  const handleShowTraceDetails = useCallback((traceId: string | null) => {
    const detailMessage = traceId
      ? `Trace ID: ${traceId}`
      : "No additional trace information is available.";
    window.alert(detailMessage);
  }, []);

  const handleRetryStatus = useCallback(() => {
    if (!status || status.kind !== "error") {
      return;
    }
    if (status.source === "file") {
      fileFormRef.current?.requestSubmit();
    } else if (status.source === "url") {
      urlFormRef.current?.requestSubmit();
    }
  }, [status]);

  const handleRetryJobs = useCallback(() => {
    if (fetchJobsRef.current) {
      void fetchJobsRef.current();
    }
  }, []);

  const togglePostBatchStep = useCallback((step: string) => {
    setSimplePostBatch((current) => {
      if (current.includes(step)) {
        return current.filter((value) => value !== step);
      }
      return [...current, step];
    });
  }, []);

  const handleSimpleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSimpleError(null);
    setSimpleSuccess(null);
    setSimpleProgress([]);

    const normalizedSources = simpleSources
      .split(/\r?\n/)
      .flatMap((line) => line.split(","))
      .map((value) => value.trim())
      .filter((value) => value.length > 0);

    if (normalizedSources.length === 0) {
      setSimpleError("Please provide at least one path or URL to ingest.");
      return;
    }

    const metadata: Record<string, unknown> = {};
    if (simpleCollection.trim()) {
      metadata.collection = simpleCollection.trim();
    }
    if (simpleAuthor.trim()) {
      metadata.author = simpleAuthor.trim();
    }
    if (simpleMetadata.trim()) {
      try {
        const parsed = JSON.parse(simpleMetadata);
        if (parsed && typeof parsed === "object") {
          Object.assign(metadata, parsed as Record<string, unknown>);
        } else {
          setSimpleError("Additional metadata must be a JSON object.");
          return;
        }
      } catch (error) {
        setSimpleError("Additional metadata must be valid JSON.");
        return;
      }
    }

    const payload: Record<string, unknown> = {
      sources: normalizedSources,
      mode: simpleMode,
      batch_size: simpleBatchSize,
      dry_run: simpleDryRun,
    };

    if (simplePostBatch.length > 0) {
      payload.post_batch = simplePostBatch;
    }
    if (Object.keys(metadata).length > 0) {
      payload.metadata = metadata;
    }

    setIsRunningSimple(true);
    let shouldRefreshJobs = false;
    try {
      const response = await fetch(`/api/ingest/simple`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const details = await readErrorDetails(response, "Simple ingest failed");
        setSimpleError(details.message);
        return;
      }

      if (!response.body) {
        setSimpleError("Ingestion API returned an empty response stream.");
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          buffer += decoder.decode();
          break;
        }
        buffer += decoder.decode(value, { stream: true });

        let newlineIndex = buffer.indexOf("\n");
        while (newlineIndex >= 0) {
          const line = buffer.slice(0, newlineIndex).trim();
          buffer = buffer.slice(newlineIndex + 1);
          if (line) {
            try {
              const event = JSON.parse(line) as SimpleIngestEvent;
              setSimpleProgress((prev) => [...prev, event]);
              if (event.event === "error") {
                setSimpleError(String(event.message ?? "Simple ingest failed"));
              }
              if (event.event === "complete") {
                shouldRefreshJobs = true;
                const processed = (event.processed as number | undefined) ?? 0;
                const queued = (event.queued as number | undefined) ?? 0;
                setSimpleSuccess(
                  `Ingest finished. Processed ${processed} and queued ${queued} item${processed + queued === 1 ? "" : "s"}.`,
                );
                if (!simpleDryRun) {
                  setSimpleSources("");
                }
              }
              if (event.event === "empty") {
                setSimpleSuccess("No supported sources were discovered.");
              }
            } catch (error) {
              console.error("Failed to parse ingest event", error, line);
            }
          }
          newlineIndex = buffer.indexOf("\n");
        }
      }

      const remaining = buffer.trim();
      if (remaining) {
        try {
          const event = JSON.parse(remaining) as SimpleIngestEvent;
          setSimpleProgress((prev) => [...prev, event]);
          if (event.event === "error") {
            setSimpleError(String(event.message ?? "Simple ingest failed"));
          }
          if (event.event === "complete") {
            shouldRefreshJobs = true;
            const processed = (event.processed as number | undefined) ?? 0;
            const queued = (event.queued as number | undefined) ?? 0;
            setSimpleSuccess(
              `Ingest finished. Processed ${processed} and queued ${queued} item${processed + queued === 1 ? "" : "s"}.`,
            );
            if (!simpleDryRun) {
              setSimpleSources("");
            }
          }
        } catch (error) {
          console.error("Failed to parse trailing ingest event", error, remaining);
        }
      }
    } catch (error) {
      const fallbackMessage =
        error instanceof Error
          ? error.message
          : typeof error === "string"
            ? error
            : "Simple ingest failed";
      const message =
        error instanceof TypeError && /fetch/i.test(error.message)
          ? "Unable to reach the ingestion service. Please verify the API is running."
          : fallbackMessage;
      setSimpleError(message);
    } finally {
      setIsRunningSimple(false);
      if (shouldRefreshJobs && fetchJobsRef.current) {
        void fetchJobsRef.current();
      }
    }
  };

  const handleFileSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStatus(null);

    const form = event.currentTarget;
    const fileInput = form.elements.namedItem("file") as HTMLInputElement | null;
    const frontmatterInput = form.elements.namedItem("frontmatter") as HTMLTextAreaElement | null;
    const file = fileInput?.files?.[0];

    if (!file) {
      setStatus({ kind: "error", message: "Please choose a file to upload.", traceId: null, source: "file" });
      return;
    }

    setIsUploadingFile(true);
    try {
      const frontmatter = frontmatterInput?.value ?? "";
      const result = await uploadFile({ file, frontmatter });
      setStatus(result);
      if (result.kind === "success") {
        form.reset();
      }
    } catch (error) {
      const fallbackMessage =
        error instanceof Error
          ? error.message
          : typeof error === "string"
            ? error
            : "Upload failed";
      const message =
        error instanceof TypeError && /fetch/i.test(error.message)
          ? "Unable to reach the ingestion service. Please verify the API is running."
          : fallbackMessage;
      setStatus({ kind: "error", message, traceId: null, source: "file" });
    } finally {
      setIsUploadingFile(false);
    }
  };

  const handleUrlSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStatus(null);

    const form = event.currentTarget;
    const urlInput = form.elements.namedItem("url") as HTMLInputElement | null;
    const sourceTypeInput = form.elements.namedItem("source_type") as HTMLSelectElement | null;
    const frontmatterInput = form.elements.namedItem("frontmatter_json") as HTMLTextAreaElement | null;

    const urlValue = urlInput?.value.trim() ?? "";
    if (!urlValue) {
      setStatus({
        kind: "error",
        message: "Please provide a URL to ingest.",
        traceId: null,
        source: "url",
      });
      return;
    }

    setIsSubmittingUrl(true);
    try {
      const result = await uploadUrl({
        url: urlValue,
        sourceType: sourceTypeInput?.value ?? "",
        frontmatter: frontmatterInput?.value ?? "",
      });
      setStatus(result);
      if (result.kind === "success") {
        form.reset();
      }
    } catch (error) {
      const fallbackMessage =
        error instanceof Error
          ? error.message
          : typeof error === "string"
            ? error
            : "URL ingestion failed";
      const message =
        error instanceof TypeError && /fetch/i.test(error.message)
          ? "Unable to reach the ingestion service. Please verify the API is running."
          : fallbackMessage;
      setStatus({ kind: "error", message, traceId: null, source: "url" });
    } finally {
      setIsSubmittingUrl(false);
    }
  };

  return (
    <section>
      <h2>Upload</h2>
      <p>
        Start with a quick ingest: paste server paths or canonical URLs and let Theo apply sensible defaults. Expand the
        advanced settings to tweak metadata or post-batch operations. Manual file and URL uploads remain available
        below.
      </p>

      <form
        ref={simpleFormRef}
        onSubmit={handleSimpleSubmit}
        aria-label="Simple ingest"
        style={{ marginBottom: "2rem" }}
      >
        <fieldset disabled={isRunningSimple} style={{ border: "1px solid #cbd5f5", padding: "1.5rem", borderRadius: "0.75rem" }}>
          <legend>Quick ingest</legend>
          <label style={{ display: "block" }}>
            Sources (one per line or comma-separated)
            <textarea
              name="sources"
              rows={4}
              placeholder={"/srv/imports/sermons\nhttps://example.com/homily"}
              value={simpleSources}
              onChange={(event) => setSimpleSources(event.target.value)}
              style={{ width: "100%", marginTop: "0.5rem" }}
              required
            />
          </label>
          <p style={{ marginTop: "0.5rem", color: "#475569" }}>
            The CLI defaults will tag new documents with the “{DEFAULT_COLLECTION}” collection and “{DEFAULT_AUTHOR}”
            author unless you override them below.
          </p>
          <details style={{ marginTop: "1.5rem" }}>
            <summary style={{ cursor: "pointer", fontWeight: 600 }}>Advanced settings</summary>
            <div style={{ display: "grid", gap: "1rem", marginTop: "1rem" }}>
              <label style={{ display: "block" }}>
                Mode
                <select
                  name="mode"
                  value={simpleMode}
                  onChange={(event) => setSimpleMode(event.target.value === "worker" ? "worker" : "api")}
                  style={{ width: "100%", marginTop: "0.25rem" }}
                >
                  <option value="api">API (synchronous)</option>
                  <option value="worker">Worker queue</option>
                </select>
              </label>
              <label style={{ display: "block" }}>
                Batch size
                <input
                  type="number"
                  min={1}
                  value={simpleBatchSize}
                  onChange={(event) => {
                    const next = Number(event.target.value);
                    setSimpleBatchSize(Number.isFinite(next) && next > 0 ? next : 1);
                  }}
                  style={{ width: "100%", marginTop: "0.25rem" }}
                />
              </label>
              <label style={{ display: "block" }}>
                Collection override
                <input
                  type="text"
                  value={simpleCollection}
                  onChange={(event) => setSimpleCollection(event.target.value)}
                  style={{ width: "100%", marginTop: "0.25rem" }}
                />
              </label>
              <label style={{ display: "block" }}>
                Author override
                <input
                  type="text"
                  value={simpleAuthor}
                  onChange={(event) => setSimpleAuthor(event.target.value)}
                  style={{ width: "100%", marginTop: "0.25rem" }}
                />
              </label>
              <label style={{ display: "block" }}>
                Additional metadata (JSON)
                <textarea
                  name="extra_metadata"
                  rows={4}
                  value={simpleMetadata}
                  onChange={(event) => setSimpleMetadata(event.target.value)}
                  placeholder='{"tags":["Advent"],"year":2024}'
                  style={{ width: "100%", marginTop: "0.25rem" }}
                />
              </label>
              <fieldset style={{ border: "1px solid #e2e8f0", borderRadius: "0.5rem", padding: "1rem" }}>
                <legend>Post-batch options</legend>
                <label style={{ display: "block", marginBottom: "0.5rem" }}>
                  <input
                    type="checkbox"
                    checked={simplePostBatch.includes("summaries")}
                    onChange={() => togglePostBatchStep("summaries")}
                  />
                  <span style={{ marginLeft: "0.5rem" }}>Generate summaries</span>
                </label>
                <label style={{ display: "block", marginBottom: "0.5rem" }}>
                  <input
                    type="checkbox"
                    checked={simplePostBatch.includes("tags")}
                    onChange={() => togglePostBatchStep("tags")}
                  />
                  <span style={{ marginLeft: "0.5rem" }}>Run metadata enrichment</span>
                </label>
                <label style={{ display: "block" }}>
                  <input
                    type="checkbox"
                    checked={simplePostBatch.includes("biblio")}
                    onChange={() => togglePostBatchStep("biblio")}
                  />
                  <span style={{ marginLeft: "0.5rem" }}>Queue bibliography refresh</span>
                </label>
              </fieldset>
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <input
                  type="checkbox"
                  checked={simpleDryRun}
                  onChange={(event) => setSimpleDryRun(event.target.checked)}
                />
                Dry run (list batches without ingesting)
              </label>
            </div>
          </details>
          <button type="submit" style={{ marginTop: "1.5rem" }}>
            {isRunningSimple ? "Running ingest…" : "Start ingest"}
          </button>
        </fieldset>
      </form>

      {simpleError ? (
        <div style={{ marginBottom: "1.5rem" }}>
          <ErrorCallout
            message={simpleError}
            onRetry={() => simpleFormRef.current?.requestSubmit()}
            retryLabel="Retry ingest"
          />
        </div>
      ) : (
        simpleSuccess && (
          <p role="status" style={{ marginBottom: "1.5rem" }}>
            {simpleSuccess}
          </p>
        )
      )}

      {simpleProgress.length > 0 && (
        <div style={{ marginBottom: "2rem" }}>
          <h3>Ingest progress</h3>
          <ol style={{ paddingLeft: "1.5rem", marginTop: "0.75rem", display: "grid", gap: "0.5rem" }}>
            {simpleProgress.map((event, index) => (
              <li key={`${event.event}-${index}`} style={{ lineHeight: 1.4 }}>
                {describeSimpleEvent(event)}
              </li>
            ))}
          </ol>
        </div>
      )}

      <details style={{ marginBottom: "2rem" }}>
        <summary style={{ cursor: "pointer", fontWeight: 600 }}>Manual uploads</summary>
        <div style={{ marginTop: "1rem", display: "grid", gap: "2rem" }}>
          <form
            ref={fileFormRef}
            onSubmit={handleFileSubmit}
            aria-label="Upload file"
            style={{ border: "1px solid #e2e8f0", padding: "1.5rem", borderRadius: "0.75rem" }}
          >
            <fieldset disabled={isUploadingFile}>
              <legend>Upload file</legend>
              <label>
                Source file
                <input type="file" name="file" required style={{ display: "block", marginTop: "0.25rem" }} />
              </label>
              <label style={{ display: "block", marginTop: "1rem" }}>
                Frontmatter (JSON)
                <textarea
                  name="frontmatter"
                  rows={4}
                  placeholder='{"collection":"Gospels"}'
                  style={{ width: "100%", marginTop: "0.25rem" }}
                />
              </label>
              <button type="submit" style={{ marginTop: "1rem" }}>
                {isUploadingFile ? "Uploading…" : "Upload file"}
              </button>
            </fieldset>
          </form>

          <form
            ref={urlFormRef}
            onSubmit={handleUrlSubmit}
            aria-label="Ingest URL"
            style={{ border: "1px solid #e2e8f0", padding: "1.5rem", borderRadius: "0.75rem" }}
          >
            <fieldset disabled={isSubmittingUrl}>
              <legend>Ingest URL</legend>
              <label style={{ display: "block" }}>
                URL
                <input type="url" name="url" placeholder="https://" required style={{ width: "100%", marginTop: "0.25rem" }} />
              </label>
              <label style={{ display: "block", marginTop: "1rem" }}>
                Source type (URLs: YouTube or Web page)
                <select name="source_type" defaultValue="" style={{ width: "100%", marginTop: "0.25rem" }}>
                  <option value="">Detect automatically</option>
                  <option value="youtube">YouTube</option>
                  <option value="html">Web page</option>
                </select>
              </label>
              <label style={{ display: "block", marginTop: "1rem" }}>
                Frontmatter (JSON)
                <textarea
                  name="frontmatter_json"
                  rows={4}
                  placeholder='{"collection":"Patristics"}'
                  style={{ width: "100%", marginTop: "0.25rem" }}
                />
              </label>
              <button type="submit" style={{ marginTop: "1rem" }}>
                {isSubmittingUrl ? "Submitting…" : "Submit URL"}
              </button>
            </fieldset>
          </form>

          {status && status.kind === "error" ? (
            <ErrorCallout
              message={status.message}
              traceId={status.traceId}
              onRetry={handleRetryStatus}
              onShowDetails={handleShowTraceDetails}
            />
          ) : (
            status && (
              <p role="status" style={{ margin: 0 }}>
                {status.message}
              </p>
            )
          )}
        </div>
      </details>

      <section style={{ marginTop: "2.5rem" }}>
        <h3>Recent jobs</h3>
        {jobError && (
          <div style={{ marginBottom: "1rem" }}>
            <ErrorCallout
              message={jobError.message}
              traceId={jobError.traceId}
              onRetry={handleRetryJobs}
              onShowDetails={handleShowTraceDetails}
            />
          </div>
        )}
        {jobs.length === 0 ? (
          <p>No jobs queued yet.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 480 }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left", padding: "0.5rem", borderBottom: "1px solid #e2e8f0" }}>Type</th>
                  <th style={{ textAlign: "left", padding: "0.5rem", borderBottom: "1px solid #e2e8f0" }}>Status</th>
                  <th style={{ textAlign: "left", padding: "0.5rem", borderBottom: "1px solid #e2e8f0" }}>Document</th>
                  <th style={{ textAlign: "left", padding: "0.5rem", borderBottom: "1px solid #e2e8f0" }}>Updated</th>
                  <th style={{ textAlign: "left", padding: "0.5rem", borderBottom: "1px solid #e2e8f0" }}>Error</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id}>
                    <td style={{ padding: "0.5rem", borderBottom: "1px solid #f1f5f9" }}>{job.job_type}</td>
                    <td style={{ padding: "0.5rem", borderBottom: "1px solid #f1f5f9" }}>{job.status}</td>
                    <td style={{ padding: "0.5rem", borderBottom: "1px solid #f1f5f9" }}>
                      {job.document_id ?? "—"}
                    </td>
                    <td style={{ padding: "0.5rem", borderBottom: "1px solid #f1f5f9" }}>{formatTimestamp(job.updated_at)}</td>
                    <td style={{ padding: "0.5rem", borderBottom: "1px solid #f1f5f9", color: job.error ? "crimson" : "#475569" }}>
                      {job.error ? job.error : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </section>
  );
}
