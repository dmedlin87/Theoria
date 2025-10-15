"use client";

import { FormEvent, useEffect, useId, useMemo, useState } from "react";

import {
  type ApiCredentials,
  useApiConfig,
  useApiConnectionTester,
} from "../../lib/api-config";
import styles from "../settings.module.css";

type SaveState =
  | { status: "idle"; message: string | null }
  | { status: "saving"; message: string | null }
  | { status: "success"; message: string }
  | { status: "error"; message: string };

const INITIAL_FORM: ApiCredentials = { authorization: null, apiKey: null };

export default function ApiAccessForm(): JSX.Element {
  const { credentials, setCredentials, clearCredentials } = useApiConfig();
  const [formState, setFormState] = useState<ApiCredentials>(INITIAL_FORM);
  const [saveStatus, setSaveStatus] = useState<SaveState>({ status: "idle", message: null });
  const { state: connectionState, testConnection, reset: resetConnection } =
    useApiConnectionTester();
  const authFieldId = useId();
  const apiKeyFieldId = useId();

  useEffect(() => {
    setFormState({
      authorization: credentials.authorization,
      apiKey: credentials.apiKey,
    });
  }, [credentials.authorization, credentials.apiKey]);

  const effectiveHeaders = useMemo(() => {
    const headers: Record<string, string> = {};
    const auth = formState.authorization?.trim();
    const key = formState.apiKey?.trim();
    if (auth) {
      headers.Authorization = auth;
    } else if (key) {
      headers[key.toLowerCase().startsWith("bearer ") ? "Authorization" : "X-API-Key"] = key;
    }
    return headers;
  }, [formState.authorization, formState.apiKey]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaveStatus({ status: "saving", message: "Saving credentials…" });
    try {
      setCredentials({
        authorization: formState.authorization?.trim() || null,
        apiKey: formState.apiKey?.trim() || null,
      });
      setSaveStatus({ status: "success", message: "Credentials saved to this browser." });
    } catch (error) {
      const message =
        error instanceof Error && error.message
          ? error.message
          : "Unable to persist credentials";
      setSaveStatus({ status: "error", message });
    }
  };

  const handleClear = () => {
    clearCredentials();
    setFormState(INITIAL_FORM);
    setSaveStatus({ status: "idle", message: null });
    resetConnection();
  };

  const renderSaveStatus = () => {
    if (saveStatus.status === "idle" || !saveStatus.message) {
      return null;
    }
    const className =
      saveStatus.status === "success"
        ? `${styles.status} ${styles.statusSuccess}`
        : `${styles.status} ${styles.statusError}`;
    return (
      <p role="status" className={className}>
        {saveStatus.message}
      </p>
    );
  };

  const renderConnectionStatus = () => {
    if (connectionState.status === "idle") {
      return null;
    }
    const className =
      connectionState.status === "success"
        ? `${styles.status} ${styles.statusSuccess}`
        : connectionState.status === "pending"
          ? `${styles.status} ${styles.statusInfo}`
          : `${styles.status} ${styles.statusError}`;
    return (
      <p role="status" className={className}>
        {connectionState.message}
      </p>
    );
  };

  return (
    <form className={styles.formGrid} onSubmit={handleSubmit} aria-labelledby={`${authFieldId}-legend`}>
      <fieldset className={styles.formGrid}>
        <legend id={`${authFieldId}-legend`} className={styles.visuallyHidden}>
          API access credentials
        </legend>
        <div className={styles.field}>
          <label htmlFor={authFieldId} className={styles.label}>
            Authorization header
          </label>
          <input
            id={authFieldId}
            className={styles.input}
            type="text"
            value={formState.authorization ?? ""}
            onChange={(event) =>
              setFormState((current) => ({ ...current, authorization: event.target.value }))
            }
            placeholder="Bearer <token>"
            autoComplete="off"
            spellCheck={false}
          />
          <p className={styles.helperText}>
            Provide the complete Authorization header value, including the <code>Bearer</code> prefix.
          </p>
        </div>

        <div className={styles.field}>
          <label htmlFor={apiKeyFieldId} className={styles.label}>
            API key (used when Authorization is empty)
          </label>
          <input
            id={apiKeyFieldId}
            className={styles.input}
            type="text"
            value={formState.apiKey ?? ""}
            onChange={(event) =>
              setFormState((current) => ({ ...current, apiKey: event.target.value }))
            }
            placeholder="theo-dev-key"
            autoComplete="off"
            spellCheck={false}
          />
          <p className={styles.helperText}>
            If provided, the UI sends this value with every request as either <code>X-API-Key</code> or
            <code>Authorization</code> when it already includes a Bearer prefix.
          </p>
        </div>
      </fieldset>

      <div className={styles.buttonRow}>
        <button
          type="submit"
          className={`${styles.button} ${styles.buttonPrimary}`}
          disabled={saveStatus.status === "saving"}
        >
          {saveStatus.status === "saving" ? "Saving…" : "Save credentials"}
        </button>
        <button
          type="button"
          className={`${styles.button} ${styles.buttonSecondary}`}
          onClick={() =>
            testConnection({
              authorization: formState.authorization?.trim() || null,
              apiKey: formState.apiKey?.trim() || null,
            })
          }
          disabled={connectionState.status === "pending"}
        >
          {connectionState.status === "pending" ? "Testing…" : "Test connection"}
        </button>
        <button
          type="button"
          className={`${styles.button} ${styles.buttonTertiary}`}
          onClick={handleClear}
        >
          Clear stored values
        </button>
      </div>

      {renderSaveStatus()}
      {renderConnectionStatus()}

      {Object.keys(effectiveHeaders).length > 0 ? (
        <p className={styles.helperText}>
          Requests will include: {Object.entries(effectiveHeaders)
            .map(([key, value]) => `${key}: ${value}`)
            .join(" · ")}
        </p>
      ) : (
        <p className={styles.helperText}>
          No credentials stored. The client will fall back to environment variables when available.
        </p>
      )}
    </form>
  );
}
