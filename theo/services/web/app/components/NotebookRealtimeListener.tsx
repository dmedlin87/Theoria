"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import styles from "./NotebookRealtimeListener.module.css";

import { getApiBaseUrl } from "../lib/api";

interface NotebookRealtimeListenerProps {
  notebookId: string;
  initialVersion: number;
  onUpdate?: (event: MessageEvent | { data: string }) => void;
}

type ConnectionState = "connecting" | "connected" | "disconnected";

function buildRealtimeUrl(notebookId: string): string {
  const baseHttp = getApiBaseUrl().replace(/\/$/, "");
  const wsUrl = baseHttp.replace(/^http/i, (value) =>
    value.toLowerCase() === "https" ? "wss" : "ws",
  );
  return `${wsUrl}/realtime/notebooks/${encodeURIComponent(notebookId)}`;
}

async function pollVersion(
  notebookId: string,
  signal: AbortSignal,
): Promise<number | null> {
  const baseHttp = getApiBaseUrl().replace(/\/$/, "");
  try {
    const response = await fetch(
      `${baseHttp}/realtime/notebooks/${encodeURIComponent(notebookId)}/poll`,
      { signal, cache: "no-store" },
    );
    if (!response.ok) {
      return null;
    }
    const payload = (await response.json()) as { version?: number };
    return typeof payload.version === "number" ? payload.version : null;
  } catch (error) {
    if ((error as Error).name === "AbortError") {
      return null;
    }
    return null;
  }
}

export default function NotebookRealtimeListener({
  notebookId,
  initialVersion,
  onUpdate,
}: NotebookRealtimeListenerProps) {
  const [state, setState] = useState<ConnectionState>("connecting");
  const [version, setVersion] = useState<number>(initialVersion);
  const wsRef = useRef<WebSocket | null>(null);
  const onUpdateRef = useRef(onUpdate);

  useEffect(() => {
    onUpdateRef.current = onUpdate;
  }, [onUpdate]);

  useEffect(() => {
    const websocket = new WebSocket(buildRealtimeUrl(notebookId));
    wsRef.current = websocket;

    websocket.onopen = () => {
      setState("connected");
    };

    websocket.onmessage = (event) => {
      if (event.data) {
        try {
          const payload = JSON.parse(event.data as string) as {
            version?: number;
          };
          if (typeof payload.version === "number") {
            setVersion(payload.version);
          }
        } catch (error) {
          console.warn("Failed to parse realtime payload", error);
        }
      }
      onUpdateRef.current?.(event);
    };

    websocket.onclose = () => {
      setState("disconnected");
    };

    websocket.onerror = () => {
      setState("disconnected");
    };

    return () => {
      websocket.close();
      wsRef.current = null;
    };
  }, [notebookId]);

  useEffect(() => {
    if (state === "connected") {
      return undefined;
    }
    const controller = new AbortController();
    const interval = window.setInterval(async () => {
      const versionValue = await pollVersion(notebookId, controller.signal);
      if (typeof versionValue === "number") {
        setVersion(versionValue);
      }
    }, 5000);
    return () => {
      controller.abort();
      window.clearInterval(interval);
    };
  }, [notebookId, state]);

  const badgeLabel = useMemo(() => {
    switch (state) {
      case "connected":
        return "Live";
      case "disconnected":
        return "Offline";
      default:
        return "Connecting";
    }
  }, [state]);

  return (
    <div className={styles.container}>
      <span className={styles.statusBadge}>
        <span
          aria-hidden
          className={`${styles.statusIndicator} ${styles[state]}`}
        />
        {badgeLabel}
      </span>
      <span className={styles.versionText}>
        Version {version}
      </span>
    </div>
  );
}
