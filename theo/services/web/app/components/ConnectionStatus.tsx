"use client";

import { useEffect, useState } from "react";
import styles from "./ConnectionStatus.module.css";

type Status = "checking" | "connected" | "disconnected";

export function ConnectionStatus() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch("/api/health", { cache: "no-store" });
        setStatus(response.ok ? "connected" : "disconnected");
      } catch {
        setStatus("disconnected");
      }
    };

    // Initial check
    checkHealth();

    // Poll every 30 seconds
    const interval = setInterval(checkHealth, 30000);

    return () => clearInterval(interval);
  }, []);

  if (status === "checking") return null;

  return (
    <div className={styles.status} data-status={status}>
      <span className={styles.dot} />
      <span className={styles.label}>
        {status === "connected" ? "API Connected" : "API Disconnected"}
      </span>
    </div>
  );
}
