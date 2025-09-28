"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { getApiBaseUrl } from "../lib/api";

type UploadStatus = {
  kind: "success" | "error" | "info";
  message: string;
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

async function readErrorMessage(response: Response, fallback: string): Promise<string> {
  const text = await response.text();
  const trimmed = text.trim();
  if (!trimmed) {
    return fallback;
  }

  try {
    const data = JSON.parse(trimmed) as {
      detail?: unknown;
      message?: unknown;
      error?: unknown;
    };
    const detailCandidates = [data.detail, data.message, data.error];
    for (const candidate of detailCandidates) {
      if (typeof candidate === "string" && candidate.trim()) {
        return candidate;
      }
    }
  } catch {
    // Fall back to the raw response text if parsing fails.
    return trimmed;
  }

  return trimmed;
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
    const message = await readErrorMessage(response, "Upload failed");
    return { kind: "error", message };
  }

  const payload = (await response.json()) as { document_id: string; status: string };
  return {
    kind: "success",
    message: `Upload complete. Document ID: ${payload.document_id}`,
  };
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
      return { kind: "error", message: "Frontmatter must be valid JSON" };
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
    const message = await readErrorMessage(response, "URL ingestion failed");
    return { kind: "error", message };
  }

  const data = (await response.json()) as { document_id: string; status: string };
  return {
    kind: "success",
    message: `URL queued. Document ID: ${data.document_id}`,
  };
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString();
}

export default function UploadPage(): JSX.Element {
  const [status, setStatus] = useState<UploadStatus | null>(null);
  const [isUploadingFile, setIsUploadingFile] = useState(false);
  const [isSubmittingUrl, setIsSubmittingUrl] = useState(false);
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [jobError, setJobError] = useState<string | null>(null);

  const baseUrl = useMemo(() => getApiBaseUrl().replace(/\/$/, ""), []);

  useEffect(() => {
    let isMounted = true;

    const fetchJobs = async () => {
      try {
        const response = await fetch(`${baseUrl}/jobs?limit=25`, { cache: "no-store" });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = (await response.json()) as { jobs: JobStatus[] };
        if (isMounted) {
          setJobs(payload.jobs ?? []);
          setJobError(null);
        }
      } catch (error) {
        if (isMounted) {
          setJobError((error as Error).message || "Unable to load jobs");
        }
      }
    };

    fetchJobs();
    const interval = window.setInterval(fetchJobs, 5000);
    return () => {
      isMounted = false;
      window.clearInterval(interval);
    };
  }, [baseUrl]);

  const handleFileSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStatus(null);

    const form = event.currentTarget;
    const fileInput = form.elements.namedItem("file") as HTMLInputElement | null;
    const frontmatterInput = form.elements.namedItem("frontmatter") as HTMLTextAreaElement | null;
    const file = fileInput?.files?.[0];

    if (!file) {
      setStatus({ kind: "error", message: "Please choose a file to upload." });
      return;
    }

    setIsUploadingFile(true);
    try {
      const frontmatter = frontmatterInput?.value ?? "";
      const result = await uploadFile({ file, frontmatter });
      setStatus(result);
      form.reset();
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
      setStatus({ kind: "error", message });
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
      setStatus({ kind: "error", message: "Please provide a URL to ingest." });
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
      form.reset();
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
      setStatus({ kind: "error", message });
    } finally {
      setIsSubmittingUrl(false);
    }
  };

  return (
    <section>
      <h2>Upload</h2>
      <p>Send a local file or a canonical URL to the ingestion pipeline.</p>

      <form onSubmit={handleFileSubmit} aria-label="Upload file" style={{ marginBottom: "2rem" }}>
        <fieldset disabled={isUploadingFile}>
          <legend>Upload file</legend>
          <label>
            Source file
            <input type="file" name="file" required />
          </label>
          <label style={{ display: "block", marginTop: "1rem" }}>
            Frontmatter (JSON)
            <textarea
              name="frontmatter"
              rows={4}
              placeholder='{"collection":"Gospels"}'
              style={{ width: "100%" }}
            />
          </label>
          <button type="submit" style={{ marginTop: "1rem" }}>
            {isUploadingFile ? "Uploading." : "Upload file"}
          </button>
        </fieldset>
      </form>

      <form onSubmit={handleUrlSubmit} aria-label="Ingest URL">
        <fieldset disabled={isSubmittingUrl}>
          <legend>Ingest URL</legend>
          <label style={{ display: "block" }}>
            URL
            <input type="url" name="url" placeholder="https://" required style={{ width: "100%" }} />
          </label>
          <label style={{ display: "block", marginTop: "1rem" }}>
            Source type (URLs: YouTube or Web page)
            <select name="source_type" defaultValue="" style={{ width: "100%" }}>
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
              style={{ width: "100%" }}
            />
          </label>
          <button type="submit" style={{ marginTop: "1rem" }}>
            {isSubmittingUrl ? "Submitting." : "Submit URL"}
          </button>
        </fieldset>
      </form>

      {status && (
        <p role={status.kind === "error" ? "alert" : "status"} style={{ marginTop: "1.5rem" }}>
          {status.message}
        </p>
      )}

      <section style={{ marginTop: "2.5rem" }}>
        <h3>Recent jobs</h3>
        {jobError && (
          <p role="alert" style={{ color: "crimson" }}>
            {jobError}
          </p>
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
