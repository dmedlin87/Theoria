"use client";

import { useEffect, useMemo, useState } from "react";

import ApiAccessForm from "./components/ApiAccessForm";
import ProviderRegistrationForm from "./components/ProviderRegistrationForm";
import ProviderSettingsCard from "./components/ProviderSettingsCard";
import {
  type ProviderSettingsResponse,
  createTheoApiClient,
} from "../lib/api-client";
import styles from "./settings.module.css";

type LoadingState = "idle" | "loading" | "error" | "loaded";

export default function SettingsPage(): JSX.Element {
  const client = useMemo(() => createTheoApiClient(), []);
  const [providers, setProviders] = useState<ProviderSettingsResponse[]>([]);
  const [state, setState] = useState<LoadingState>("idle");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const loadProviders = async () => {
      setState("loading");
      setError(null);
      try {
        const response = await client.listProviderSettings();
        if (!cancelled) {
          setProviders(response);
          setState("loaded");
        }
      } catch (loadError) {
        if (cancelled) {
          return;
        }
        const message =
          loadError instanceof Error && loadError.message
            ? loadError.message
            : "Unable to load provider settings";
        setError(message);
        setState("error");
      }
    };
    loadProviders();
    return () => {
      cancelled = true;
    };
  }, [client]);

  const sortedProviders = useMemo(() => {
    return [...providers].sort((a, b) => a.provider.localeCompare(b.provider));
  }, [providers]);

  const handleProviderChange = (next: ProviderSettingsResponse) => {
    setProviders((current) => {
      const existingIndex = current.findIndex((entry) => entry.provider === next.provider);
      if (existingIndex >= 0) {
        const updated = [...current];
        updated[existingIndex] = next;
        return updated;
      }
      return [...current, next];
    });
  };

  return (
    <div className={styles.page}>
      <section className={styles.section} aria-labelledby="api-access-title">
        <div className={styles.sectionHeader}>
          <h1 id="api-access-title" className={styles.sectionTitle}>
            API access
          </h1>
          <span className={styles.sectionTag}>Local override</span>
        </div>
        <p className={styles.sectionDescription}>
          Store credentials in your browser so every request to the Theoria API includes the correct
          Authorization or API key headers.
        </p>
        <div className={styles.sectionBody}>
          <ApiAccessForm />
        </div>
      </section>

      <section className={styles.section} aria-labelledby="providers-title">
        <div className={styles.sectionHeader}>
          <h2 id="providers-title" className={styles.sectionTitle}>
            AI provider credentials
          </h2>
        </div>
        <div className={styles.sectionBody}>
          {state === "loading" ? (
            <p className={styles.helperText}>Loading providers…</p>
          ) : null}
          {state === "error" && error ? (
            <p className={`${styles.status} ${styles.statusError}`} role="alert">
              {error}
            </p>
          ) : null}
          {state === "loaded" && sortedProviders.length === 0 ? (
            <div className={styles.emptyState} role="status">
              No providers registered yet. Add one below to wire credentials and defaults.
            </div>
          ) : null}
          {sortedProviders.length > 0 ? (
            <div className={styles.cardGrid}>
              {sortedProviders.map((provider) => (
                <ProviderSettingsCard
                  key={provider.provider}
                  provider={provider}
                  client={client}
                  onChange={handleProviderChange}
                />
              ))}
            </div>
          ) : null}

          <ProviderRegistrationForm client={client} onCreated={handleProviderChange} />
        </div>
      </section>
    </div>
  );
}
