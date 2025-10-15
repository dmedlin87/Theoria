"use client";

import { FormEvent, useEffect, useId, useMemo, useState } from "react";

import type {
  ProviderSettingsRequest,
  ProviderSettingsResponse,
  TheoApiClient,
} from "../../lib/api-client";
import styles from "../settings.module.css";

type ProviderSettingsCardProps = {
  provider: ProviderSettingsResponse;
  client: TheoApiClient;
  onChange: (next: ProviderSettingsResponse) => void;
};

type OperationState =
  | { status: "idle"; message: string | null }
  | { status: "saving"; message: string | null }
  | { status: "success"; message: string }
  | { status: "error"; message: string };

function formatHeaders(headers: Record<string, string> | null | undefined): string {
  if (!headers || Object.keys(headers).length === 0) {
    return "";
  }
  return JSON.stringify(headers, null, 2);
}

function parseHeaders(value: string): Record<string, string> | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      const invalidKeys = new Set(["__proto__", "prototype", "constructor"]);
      const headers = Object.create(null) as Record<string, string>;
      for (const [key, value] of Object.entries(parsed as Record<string, unknown>)) {
        if (invalidKeys.has(key)) {
          throw new Error(`Invalid header key: ${key}`);
        }
        if (typeof value === "string") {
          headers[key] = value;
        }
      }
      return headers;
    }
    throw new Error("Headers must be a JSON object");
  } catch (error) {
    if (error instanceof Error) {
      throw new Error(`Invalid headers JSON: ${error.message}`);
    }
    throw new Error("Invalid headers JSON");
  }
}

export default function ProviderSettingsCard({
  provider,
  client,
  onChange,
}: ProviderSettingsCardProps): JSX.Element {
  const titleId = useId();
  const descriptionId = useId();
  const baseUrlId = useId();
  const modelId = useId();
  const headersId = useId();
  const apiKeyId = useId();

  const [baseUrl, setBaseUrl] = useState(provider.base_url ?? "");
  const [defaultModel, setDefaultModel] = useState(provider.default_model ?? "");
  const [headersInput, setHeadersInput] = useState(formatHeaders(provider.extra_headers));
  const [apiKey, setApiKey] = useState("");
  const [status, setStatus] = useState<OperationState>({ status: "idle", message: null });

  useEffect(() => {
    setBaseUrl(provider.base_url ?? "");
    setDefaultModel(provider.default_model ?? "");
    setHeadersInput(formatHeaders(provider.extra_headers));
    setApiKey("");
  }, [provider.base_url, provider.default_model, provider.extra_headers]);

  useEffect(() => {
    setStatus({ status: "idle", message: null });
  }, [provider.provider]);

  const apiKeyConfigured = provider.has_api_key;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const payload: ProviderSettingsRequest = {};
    if (baseUrl.trim()) {
      payload.base_url = baseUrl.trim();
    } else {
      payload.base_url = null;
    }
    if (defaultModel.trim()) {
      payload.default_model = defaultModel.trim();
    } else {
      payload.default_model = null;
    }

    try {
      payload.extra_headers = parseHeaders(headersInput);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Invalid headers";
      setStatus({ status: "error", message });
      return;
    }

    if (apiKey.trim()) {
      payload.api_key = apiKey.trim();
    }

    setStatus({ status: "saving", message: "Saving provider settings…" });
    try {
      const result = await client.upsertProviderSettings(provider.provider, payload);
      onChange(result);
      setApiKey("");
      setStatus({ status: "success", message: "Provider settings saved." });
    } catch (error) {
      const message =
        error instanceof Error && error.message ? error.message : "Failed to save provider";
      setStatus({ status: "error", message });
    }
  };

  const handleClearApiKey = async () => {
    setStatus({ status: "saving", message: "Removing API key…" });
    try {
      const result = await client.upsertProviderSettings(provider.provider, { api_key: null });
      onChange(result);
      setStatus({ status: "success", message: "API key cleared for this provider." });
    } catch (error) {
      const message =
        error instanceof Error && error.message
          ? error.message
          : "Unable to clear API key";
      setStatus({ status: "error", message });
    }
  };

  const statusClass = useMemo(() => {
    switch (status.status) {
      case "success":
        return `${styles.status} ${styles.statusSuccess}`;
      case "error":
        return `${styles.status} ${styles.statusError}`;
      case "saving":
        return `${styles.status} ${styles.statusInfo}`;
      default:
        return `${styles.status} ${styles.statusInfo}`;
    }
  }, [status.status]);

  return (
    <article className={styles.card} aria-labelledby={titleId} aria-describedby={descriptionId}>
      <header className={styles.cardHeader}>
        <h3 id={titleId} className={styles.cardTitle}>
          {provider.provider}
        </h3>
        <span className={styles.badge} aria-live="polite">
          {apiKeyConfigured ? "API key configured" : "API key missing"}
        </span>
      </header>
      <p id={descriptionId} className={styles.helperText}>
        Configure the base URL, default model, and optional headers for this provider. API keys are
        never displayed once saved—enter a new value to rotate the credential.
      </p>
      <form className={styles.formGrid} onSubmit={handleSubmit}>
        <div className={styles.field}>
          <label htmlFor={baseUrlId} className={styles.label}>
            Base URL
          </label>
          <input
            id={baseUrlId}
            className={styles.input}
            type="url"
            value={baseUrl}
            onChange={(event) => setBaseUrl(event.target.value)}
            placeholder="https://api.openai.com"
          />
        </div>

        <div className={styles.field}>
          <label htmlFor={modelId} className={styles.label}>
            Default model
          </label>
          <input
            id={modelId}
            className={styles.input}
            type="text"
            value={defaultModel}
            onChange={(event) => setDefaultModel(event.target.value)}
            placeholder="gpt-4o"
            autoComplete="off"
          />
        </div>

        <div className={styles.field}>
          <label htmlFor={headersId} className={styles.label}>
            Extra headers (JSON)
          </label>
          <textarea
            id={headersId}
            className={styles.textarea}
            value={headersInput}
            onChange={(event) => setHeadersInput(event.target.value)}
            placeholder={`{
  "X-Organization": "Research"
}`}
          />
          <p className={styles.helperText}>Provide additional headers as a JSON object.</p>
        </div>

        <div className={styles.field}>
          <label htmlFor={apiKeyId} className={styles.label}>
            API key (new value)
          </label>
          <input
            id={apiKeyId}
            className={styles.input}
            type="password"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            placeholder="••••••"
            autoComplete="off"
          />
          <p className={styles.helperText}>
            Enter a new key to rotate credentials. Leave blank to keep the existing secret.
          </p>
        </div>

        <div className={styles.buttonRow}>
          <button
            type="submit"
            className={`${styles.button} ${styles.buttonPrimary}`}
            disabled={status.status === "saving"}
          >
            {status.status === "saving" ? "Saving…" : "Save provider"}
          </button>
          <button
            type="button"
            className={`${styles.button} ${styles.buttonSecondary}`}
            onClick={handleClearApiKey}
            disabled={status.status === "saving" || !apiKeyConfigured}
          >
            Remove API key
          </button>
        </div>

        {status.message ? (
          <p role="status" className={statusClass}>
            {status.message}
          </p>
        ) : null}
      </form>
    </article>
  );
}
