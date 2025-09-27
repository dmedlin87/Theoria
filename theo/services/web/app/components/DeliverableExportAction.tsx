"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { getApiBaseUrl } from "../lib/api";

type DeliverableFormat = "markdown" | "ndjson" | "csv";

interface DeliverableAsset {
  format: DeliverableFormat;
  filename: string;
  media_type: string;
  content: string;
}

interface DeliverableManifest {
  export_id: string;
  schema_version: string;
  generated_at: string;
  type: string;
  model_preset?: string | null;
  sources?: string[];
}

interface DeliverableResponsePayload {
  export_id: string;
  status: "queued" | "processing" | "completed" | "failed";
  manifest: DeliverableManifest;
  assets: DeliverableAsset[];
  message?: string | null;
}

export interface DeliverableRequestPayload {
  type: "sermon" | "transcript";
  formats?: DeliverableFormat[];
  topic?: string;
  osis?: string | null;
  filters?: Record<string, unknown>;
  model?: string | null;
  document_id?: string;
}

interface DownloadLink {
  url: string;
  filename: string;
  mediaType: string;
}

interface DeliverableExportActionProps {
  label: string;
  requestPayload: DeliverableRequestPayload;
  preparingText?: string;
  successText?: string;
  idleText?: string;
}

function revokeUrls(links: DownloadLink[]) {
  links.forEach((link) => URL.revokeObjectURL(link.url));
}

export default function DeliverableExportAction({
  label,
  requestPayload,
  preparingText = "Preparing deliverable…",
  successText = "Export ready.",
  idleText,
}: DeliverableExportActionProps) {
  const baseUrl = useMemo(() => getApiBaseUrl().replace(/\/$/, ""), []);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">(
    "idle",
  );
  const [message, setMessage] = useState<string | null>(idleText ?? null);
  const [manifest, setManifest] = useState<DeliverableManifest | null>(null);
  const [downloads, setDownloads] = useState<DownloadLink[]>([]);

  useEffect(() => () => revokeUrls(downloads), [downloads]);

  const handleClick = useCallback(async () => {
    if (status === "loading") {
      return;
    }
    setStatus("loading");
    setMessage(preparingText);
    setManifest(null);
    setDownloads((previous) => {
      revokeUrls(previous);
      return [];
    });

    try {
      const response = await fetch(`${baseUrl}/export/deliverable`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          formats: requestPayload.formats ?? ["markdown"],
          ...requestPayload,
        }),
      });
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || response.statusText);
      }
      const payload = (await response.json()) as DeliverableResponsePayload;
      if (payload.status !== "completed") {
        throw new Error(payload.message || "Export did not complete");
      }
      if (!payload.assets || payload.assets.length === 0) {
        throw new Error("Export returned no assets");
      }
      const preparedDownloads: DownloadLink[] = payload.assets.map((asset) => {
        const blob = new Blob([asset.content], { type: asset.media_type });
        return {
          url: URL.createObjectURL(blob),
          filename: asset.filename,
          mediaType: asset.media_type,
        };
      });
      setDownloads(preparedDownloads);
      setManifest(payload.manifest);
      setStatus("success");
      setMessage(successText);
    } catch (error) {
      setStatus("error");
      setMessage((error as Error).message || "Unable to generate export");
    }
  }, [baseUrl, preparingText, requestPayload, status, successText]);

  return (
    <div style={{ display: "grid", gap: "0.5rem", alignItems: "start" }}>
      <button type="button" onClick={handleClick} disabled={status === "loading"}>
        {status === "loading" ? preparingText : label}
      </button>
      {message && (
        <p
          role={status === "error" ? "alert" : "status"}
          style={{
            color: status === "error" ? "var(--danger, #b91c1c)" : "inherit",
            margin: 0,
          }}
        >
          {message}
          {manifest && status === "success" ? (
            <>
              {" "}• Export ID: {manifest.export_id} ({new Date(manifest.generated_at).toLocaleString()})
            </>
          ) : null}
        </p>
      )}
      {downloads.length > 0 ? (
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.35rem" }}>
          {downloads.map((download) => (
            <li key={download.filename}>
              <a href={download.url} download={download.filename}>
                Download {download.filename}
              </a>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
