"use client";

import { FormEvent, useState } from "react";

type UploadStatus = {
  kind: "success" | "error" | "info";
  message: string;
};

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
    const detail = await response.text();
    return { kind: "error", message: detail || "Upload failed" };
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
    const detail = await response.text();
    return { kind: "error", message: detail || "URL ingestion failed" };
  }

  const data = (await response.json()) as { document_id: string; status: string };
  return {
    kind: "success",
    message: `URL queued. Document ID: ${data.document_id}`,
  };
}

export default function UploadPage() {
  const [status, setStatus] = useState<UploadStatus | null>(null);
  const [isUploadingFile, setIsUploadingFile] = useState(false);
  const [isSubmittingUrl, setIsSubmittingUrl] = useState(false);

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
      setStatus({ kind: "error", message: (error as Error).message });
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
      setStatus({ kind: "error", message: (error as Error).message });
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
            {isUploadingFile ? "Uploading…" : "Upload file"}
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
            Source type
            <select name="source_type" defaultValue="" style={{ width: "100%" }}>
              <option value="">Detect automatically</option>
              <option value="youtube">YouTube</option>
              <option value="html">Web page</option>
              <option value="pdf">PDF</option>
              <option value="audio">Audio</option>
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
            {isSubmittingUrl ? "Submitting…" : "Submit URL"}
          </button>
        </fieldset>
      </form>

      {status && (
        <p role={status.kind === "error" ? "alert" : "status"} style={{ marginTop: "1.5rem" }}>
          {status.message}
        </p>
      )}
    </section>
  );
}
