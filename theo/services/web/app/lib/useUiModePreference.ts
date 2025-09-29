"use client";

import { useCallback, useEffect, useState } from "react";

export type UiMode = "simple" | "advanced";

const UI_MODE_STORAGE_KEY = "theo.uiMode";

function isUiMode(value: string | null): value is UiMode {
  return value === "simple" || value === "advanced";
}

export function useUiModePreference(
  defaultMode: UiMode = "simple",
): [UiMode, (mode: UiMode) => void, boolean] {
  const [mode, setMode] = useState<UiMode>(defaultMode);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const stored = window.localStorage.getItem(UI_MODE_STORAGE_KEY);
    if (isUiMode(stored)) {
      setMode(stored);
    }
    setHydrated(true);
  }, []);

  const updateMode = useCallback((next: UiMode) => {
    setMode(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(UI_MODE_STORAGE_KEY, next);
    }
  }, []);

  return [mode, updateMode, hydrated];
}
