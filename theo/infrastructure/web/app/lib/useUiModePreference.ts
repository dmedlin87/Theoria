"use client";

import { useCallback, useState } from "react";

export type UiMode = "simple" | "advanced";

const UI_MODE_STORAGE_KEY = "theo.uiMode";

function isUiMode(value: string | null): value is UiMode {
  return value === "simple" || value === "advanced";
}

export function useUiModePreference(
  defaultMode: UiMode = "simple",
): [UiMode, (mode: UiMode) => void] {
  const [mode, setMode] = useState<UiMode>(() => {
    if (typeof window === "undefined") {
      return defaultMode;
    }
    const stored = window.localStorage.getItem(UI_MODE_STORAGE_KEY);
    if (isUiMode(stored)) {
      return stored;
    }
    if (stored) {
      window.localStorage.removeItem(UI_MODE_STORAGE_KEY);
    }
    return defaultMode;
  });

  const updateMode = useCallback((next: UiMode) => {
    setMode(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(UI_MODE_STORAGE_KEY, next);
    }
  }, []);

  return [mode, updateMode];
}
