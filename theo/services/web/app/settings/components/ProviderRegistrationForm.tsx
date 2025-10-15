"use client";

import { FormEvent, useId, useState } from "react";

import type {
  ProviderSettingsRequest,
  ProviderSettingsResponse,
  TheoApiClient,
} from "../../lib/api-client";
import styles from "../settings.module.css";

type RegistrationFormProps = {
  client: TheoApiClient;
  onCreated: (provider: ProviderSettingsResponse) => void;
};

type FormState = {
  providerId: string;
  baseUrl: string;
  defaultModel: string;
  apiKey: string;
};

type RegistrationStatus =
  | { status: "idle"; message: string | null }
  | { status: "saving"; message: string | null }
  | { status: "success"; message: string }
  | { status: "error"; message: string };

const INITIAL_STATE: FormState = {
  providerId: "",
  baseUrl: "",
  defaultModel: "",
  apiKey: "",
};

export default function ProviderRegistrationForm({ client, onCreated }: RegistrationFormProps) {
  const providerId = useId();
  const baseUrlId = useId();
  const modelId = useId();
  const apiKeyId = useId();
  const [formState, setFormState] = useState<FormState>(INITIAL_STATE);
  const [status, setStatus] = useState<RegistrationStatus>({ status: "idle", message: null });

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!formState.providerId.trim()) {
      setStatus({ status: "error", message: "Provider name is required." });
      return;
    }

    const payload: ProviderSettingsRequest = {};
    if (formState.baseUrl.trim()) {
      payload.base_url = formState.baseUrl.trim();
    }
    if (formState.defaultModel.trim()) {
      payload.default_model = formState.defaultModel.trim();
    }
    if (formState.apiKey.trim()) {
      payload.api_key = formState.apiKey.trim();
    }

    setStatus({ status: "saving", message: "Registering provider…" });
    try {
      const result = await client.upsertProviderSettings(formState.providerId.trim(), payload);
      onCreated(result);
      setFormState(INITIAL_STATE);
      setStatus({ status: "success", message: "Provider registered." });
    } catch (error) {
      const message =
        error instanceof Error && error.message
          ? error.message
          : "Failed to register provider";
      setStatus({ status: "error", message });
    }
  };

  return (
    <form className={styles.formGrid} onSubmit={handleSubmit} aria-labelledby={`${providerId}-legend`}>
      <fieldset className={styles.formGrid}>
        <legend id={`${providerId}-legend`} className={styles.label}>
          Register a new provider
        </legend>
        <div className={styles.field}>
          <label htmlFor={providerId} className={styles.label}>
            Provider name
          </label>
          <input
            id={providerId}
            className={styles.input}
            type="text"
            value={formState.providerId}
            onChange={(event) =>
              setFormState((current) => ({ ...current, providerId: event.target.value }))
            }
            placeholder="openai"
            autoComplete="off"
            required
          />
        </div>

        <div className={styles.field}>
          <label htmlFor={baseUrlId} className={styles.label}>
            Base URL (optional)
          </label>
          <input
            id={baseUrlId}
            className={styles.input}
            type="url"
            value={formState.baseUrl}
            onChange={(event) =>
              setFormState((current) => ({ ...current, baseUrl: event.target.value }))
            }
            placeholder="https://api.example.com"
          />
        </div>

        <div className={styles.field}>
          <label htmlFor={modelId} className={styles.label}>
            Default model (optional)
          </label>
          <input
            id={modelId}
            className={styles.input}
            type="text"
            value={formState.defaultModel}
            onChange={(event) =>
              setFormState((current) => ({ ...current, defaultModel: event.target.value }))
            }
            placeholder="gpt-4o"
          />
        </div>

        <div className={styles.field}>
          <label htmlFor={apiKeyId} className={styles.label}>
            Initial API key
          </label>
          <input
            id={apiKeyId}
            className={styles.input}
            type="password"
            value={formState.apiKey}
            onChange={(event) =>
              setFormState((current) => ({ ...current, apiKey: event.target.value }))
            }
            placeholder="••••••"
            autoComplete="off"
          />
        </div>
      </fieldset>

      <div className={styles.buttonRow}>
        <button
          type="submit"
          className={`${styles.button} ${styles.buttonPrimary}`}
          disabled={status.status === "saving"}
        >
          {status.status === "saving" ? "Registering…" : "Register provider"}
        </button>
      </div>

      {status.message ? (
        <p
          role="status"
          className={
            status.status === "error"
              ? `${styles.status} ${styles.statusError}`
              : `${styles.status} ${styles.statusSuccess}`
          }
        >
          {status.message}
        </p>
      ) : null}
    </form>
  );
}
