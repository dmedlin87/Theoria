"use client";

import { useState } from "react";
import styles from "./settings.module.css";

export default function SettingsPage() {
  const [apiKey, setApiKey] = useState(() => {
    // Load API key from localStorage on mount
    if (typeof window !== "undefined") {
      return localStorage.getItem("theoria.apiKey") || "";
    }
    return "";
  });
  const [testStatus, setTestStatus] = useState<"idle" | "testing" | "success" | "error">("idle");
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    localStorage.setItem("theoria.apiKey", apiKey);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleTestConnection = async () => {
    setTestStatus("testing");
    try {
      const response = await fetch("/api/health", {
        headers: apiKey ? { "X-API-Key": apiKey } : {},
        cache: "no-store"
      });
      setTestStatus(response.ok ? "success" : "error");
    } catch {
      setTestStatus("error");
    }
    setTimeout(() => setTestStatus("idle"), 3000);
  };

  return (
    <section className={styles.page}>
      <div className={styles.header}>
        <h1>Settings</h1>
        <p className={styles.subtitle}>Configure your Theoria research workspace</p>
      </div>
      
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2>API Configuration</h2>
          <p className={styles.sectionDescription}>
            Configure your API credentials to access Theoria services
          </p>
        </div>

        <div className={styles.field}>
          <label htmlFor="api-key">API Key</label>
          <input
            id="api-key"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Enter your API key"
            className={styles.input}
          />
          <p className={styles.help}>
            Required to access Theoria services. Leave blank for anonymous mode (development only).
          </p>
        </div>
        
        <div className={styles.actions}>
          <button 
            onClick={handleSave} 
            className={styles.buttonPrimary}
            disabled={saved}
          >
            {saved ? "✓ Saved" : "Save"}
          </button>

          <button 
            onClick={handleTestConnection} 
            className={styles.buttonSecondary}
            disabled={testStatus === "testing"}
          >
            {testStatus === "testing" ? "Testing..." : "Test Connection"}
          </button>
        </div>
        
        {testStatus === "success" && (
          <div className={styles.success}>✓ Connection successful - API is reachable</div>
        )}
        {testStatus === "error" && (
          <div className={styles.error}>✗ Connection failed - Check your API key and network</div>
        )}
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2>AI Providers</h2>
          <p className={styles.sectionDescription}>
            Configure provider-specific credentials (OpenAI, Anthropic, etc.)
          </p>
        </div>
        <p className={styles.muted}>Coming soon: Provider-specific API key management</p>
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2>Preferences</h2>
          <p className={styles.sectionDescription}>
            Customize your research workspace defaults
          </p>
        </div>
        <p className={styles.muted}>Coming soon: Default mode, search filters, export templates</p>
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2>About</h2>
        </div>
        <div className={styles.about}>
          <p><strong>Theoria</strong> - Research engine for theology</p>
          <p className={styles.muted}>
            A modern workspace for scripture-anchored research with AI-powered assistance
          </p>
        </div>
      </div>
    </section>
  );
}
