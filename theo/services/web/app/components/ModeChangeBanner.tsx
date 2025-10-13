"use client";

import { useEffect, useRef, useState, useTransition } from "react";

import { useMode } from "../mode-context";

interface ModeChangeBannerProps {
  area: string;
}

export default function ModeChangeBanner({ area }: ModeChangeBannerProps) {
  const { mode } = useMode();
  const previousMode = useRef(mode.id);
  const [message, setMessage] = useState<string | null>(null);
  const [, startTransition] = useTransition();

  useEffect(() => {
    if (previousMode.current !== mode.id) {
      const emphasis = mode.emphasis.length
        ? mode.emphasis.join(", ")
        : "no particular emphasis";
      const suppressions = mode.suppressions.length
        ? mode.suppressions.join(", ")
        : "no major suppressions";
      startTransition(() => {
        setMessage(
          `Switched to ${mode.label} mode for ${area}. Highlighting ${emphasis} while softening ${suppressions}.`,
        );
      });
      previousMode.current = mode.id;
    }
  }, [mode, area, startTransition]);

  useEffect(() => {
    if (!message) {
      return;
    }
    const timeout = window.setTimeout(() => setMessage(null), 4000);
    return () => window.clearTimeout(timeout);
  }, [message]);

  if (!message) {
    return null;
  }

  return (
    <div
      role="status"
      style={{
        margin: "0.75rem 0",
        padding: "0.75rem 1rem",
        borderRadius: "0.75rem",
        background: "rgba(37, 99, 235, 0.1)",
        color: "#1d4ed8",
        border: "1px solid rgba(37, 99, 235, 0.2)",
        fontSize: "0.9rem",
      }}
    >
      {message}
    </div>
  );
}
