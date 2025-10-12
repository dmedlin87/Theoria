"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import ErrorCallout from "../components/ErrorCallout";
import { getApiBaseUrl } from "../lib/api";
import { type ErrorDetails, parseErrorResponse } from "../lib/errorUtils";
import FileUploadForm from "./components/FileUploadForm";
import JobsTable from "./components/JobsTable";
import SimpleIngestForm, { type SimpleIngestEvent } from "./components/SimpleIngestForm";
import UrlIngestForm from "./components/UrlIngestForm";

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

async function readErrorDetails(response: Response, fallback: string): Promise<ErrorDetails> {
  return parseErrorResponse(response, fallback);
}

export default function UploadPage(): JSX.Element {
  const [simpleProgress, setSimpleProgress] = useState<SimpleIngestEvent[]>([]);
  const [simpleError, setSimpleError] = useState<string | null>(null);
  const [simpleSuccess, setSimpleSuccess] = useState<string | null>(null);
  const [isRunningSimple, setIsRunningSimple] = useState(false);
  const simpleIngestAbortControllerRef = useRef<AbortController | null>(null);

  const [status, setStatus] = useState<UploadStatus | null>(null);
  const [isUploadingFile, setIsUploadingFile] = useState(false);
  const [isSubmittingUrl, setIsSubmittingUrl] = useState(false);
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [jobError, setJobError] = useState<ErrorDetails | null>(null);
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

  const handleRetryJobs = useCallback(() => {
    if (fetchJobsRef.current) {
      void fetchJobsRef.current();
    }
  }, []);

  const handleSimpleIngestSubmit = async (payload: {
    sources: string[];
    mode: "api" | "worker";
    batch_size: number;
    dry_run: boolean;
    post_batch?: string[];
    metadata?: Record<string, unknown>;
  }) => {
    setSimpleError(null);
    setSimpleSuccess(null);
    setSimpleProgress([]);

    if (payload.sources.length === 0) {
      setSimpleError("Please provide at least one path or URL to ingest.");
      return;
    }

    simpleIngestAbortControllerRef.current?.abort();
    const controller = new AbortController();
    simpleIngestAbortControllerRef.current = controller;

    setIsRunningSimple(true);
    let shouldRefreshJobs = false;
    try {
      const response = await fetch(`/api/ingest/simple`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
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
          }
        } catch (error) {
          console.error("Failed to parse trailing ingest event", error, remaining);
        }
      }
    } catch (error) {
      if (
        (typeof DOMException !== "undefined" && error instanceof DOMException && error.name === "AbortError") ||
        (error instanceof Error && error.name === "AbortError")
      ) {
        return;
      }
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
      if (simpleIngestAbortControllerRef.current === controller) {
        simpleIngestAbortControllerRef.current = null;
      }
      setIsRunningSimple(false);
      if (shouldRefreshJobs && fetchJobsRef.current) {
        void fetchJobsRef.current();
      }
    }
  };

  useEffect(() => {
    return () => {
      simpleIngestAbortControllerRef.current?.abort();
      simpleIngestAbortControllerRef.current = null;
    };
  }, []);

  const handleFileUpload = async (file: File, frontmatter: string) => {
    setStatus(null);
    setIsUploadingFile(true);

    try {
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
        setStatus({ kind: "error", message, traceId, source: "file" });
        return;
      }

      const payload = (await response.json()) as { document_id: string; status: string };
      setStatus({
        kind: "success",
        message: `Upload complete. Document ID: ${payload.document_id}`,
        traceId: null,
        source: "file",
      });

      if (fetchJobsRef.current) {
        void fetchJobsRef.current();
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

  const handleUrlIngest = async (url: string, sourceType: string, frontmatter: string) => {
    setStatus(null);
    setIsSubmittingUrl(true);

    try {
      let parsedFrontmatter: unknown = undefined;
      if (frontmatter.trim()) {
        try {
          parsedFrontmatter = JSON.parse(frontmatter);
        } catch {
          setStatus({
            kind: "error",
            message: "Frontmatter must be valid JSON",
            traceId: null,
            source: "url",
          });
          setIsSubmittingUrl(false);
          return;
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
        setStatus({ kind: "error", message, traceId, source: "url" });
        return;
      }

      const data = (await response.json()) as { document_id: string; status: string };
      setStatus({
        kind: "success",
        message: `URL queued. Document ID: ${data.document_id}`,
        traceId: null,
        source: "url",
      });

      if (fetchJobsRef.current) {
        void fetchJobsRef.current();
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
    <section className="upload-page">
      <h2 className="page-title">Upload</h2>
      <p className="page-description">
        Start with a quick ingest: paste server paths or canonical URLs and let Theo apply sensible defaults. Expand
        the advanced settings to tweak metadata or post-batch operations. Manual file and URL uploads remain available
        below.
      </p>

      <SimpleIngestForm
        onSubmit={handleSimpleIngestSubmit}
        isRunning={isRunningSimple}
        error={simpleError}
        success={simpleSuccess}
        progress={simpleProgress}
      />

      <details className="upload-manual-section">
        <summary className="upload-manual-summary">Manual uploads</summary>
        <div className="upload-manual-forms">
          <FileUploadForm onUpload={handleFileUpload} isUploading={isUploadingFile} />
          <UrlIngestForm onIngest={handleUrlIngest} isSubmitting={isSubmittingUrl} />

          {status && status.kind === "error" ? (
            <ErrorCallout
              message={status.message}
              traceId={status.traceId}
              onShowDetails={handleShowTraceDetails}
            />
          ) : (
            status && (
              <div className="alert alert-success" role="status">
                <div className="alert__message">{status.message}</div>
              </div>
            )
          )}
        </div>
      </details>

      <section className="upload-jobs-section">
        <h3 className="section-title">Recent jobs</h3>
        {jobError && (
          <div className="mb-3">
            <ErrorCallout
              message={jobError.message}
              traceId={jobError.traceId}
              onRetry={handleRetryJobs}
              onShowDetails={handleShowTraceDetails}
            />
          </div>
        )}
        <JobsTable jobs={jobs} />
      </section>
    </section>
  );
}
