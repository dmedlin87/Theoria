"use client";

import { useCallback, useMemo, useState } from "react";

import { getApiBaseUrl } from "../lib/api";
import styles from "./DeliverableExportAction.module.css";

type DeliverableFormat = "markdown" | "ndjson" | "csv" | "pdf";

interface DeliverableDownloadDescriptor {
  format: DeliverableFormat;
  filename: string;
  media_type: string;
  storage_path: string;
  public_url?: string | null;
  signed_url?: string | null;
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
  manifest?: DeliverableManifest | null;
  manifest_path?: string | null;
  job_id?: string | null;
  assets: DeliverableDownloadDescriptor[];
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
  href: string;
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

  const handleClick = useCallback(async () => {
    if (status === "loading") {
      return;
    }
    setStatus("loading");
    setMessage(preparingText);
    setManifest(null);
    setDownloads([]);

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
      if (!payload.assets || payload.assets.length === 0) {
        throw new Error("Export returned no assets");
      }
      const toAbsoluteUrl = (url: string) => {
        if (/^https?:\/\//.test(url)) {
          return url;
        }
        if (url.startsWith("/")) {
          return `${baseUrl}${url}`;
        }
        return `${baseUrl}/${url}`;
      };
      const preparedDownloads: DownloadLink[] = payload.assets
        .map((asset) => {
          const candidate = asset.signed_url || asset.public_url || asset.storage_path;
          if (!candidate) {
            return null;
          }
          return {
            href: toAbsoluteUrl(candidate),
            filename: asset.filename,
            mediaType: asset.media_type,
          };
        })
        .filter((entry): entry is DownloadLink => Boolean(entry));
      if (preparedDownloads.length === 0) {
        throw new Error("Export did not include downloadable URLs");
      }
      setDownloads(preparedDownloads);
      setManifest(payload.manifest ?? null);
      setStatus("success");
      setMessage(payload.message || (payload.status === "queued" ? "Export queued." : successText));
    } catch (error) {
      setStatus("error");
      setMessage((error as Error).message || "Unable to generate export");
    }
  }, [baseUrl, preparingText, requestPayload, status, successText]);

  return (
    <div className={styles.container}>
      <button type="button" onClick={handleClick} disabled={status === "loading"}>
        {status === "loading" ? preparingText : label}
      </button>
      {message && (
        <p
          role={status === "error" ? "alert" : "status"}
          className={`${styles.message} ${status === "error" ? styles.messageError : ""}`}
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
        <ul className={styles.downloadsList}>
          {downloads.map((download) => (
            <li key={download.filename}>
              <a href={download.href} download={download.filename}>
                Download {download.filename}
              </a>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
