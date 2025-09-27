"use client";

import {
  ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";

import {
  DEFAULT_MODE_ID,
  MODE_STORAGE_KEY,
  MODE_COOKIE_KEY,
  RESEARCH_MODES,
  ResearchMode,
  ResearchModeId,
  formatEmphasisSummary,
  isResearchModeId,
} from "./mode-config";

type ModeContextValue = {
  mode: ResearchMode;
  setMode: (mode: ResearchModeId) => void;
  modes: ResearchMode[];
};

const ModeContext = createContext<ModeContextValue | undefined>(undefined);

interface ModeProviderProps {
  initialMode?: ResearchModeId;
  children: ReactNode;
}

export function ModeProvider({ initialMode, children }: ModeProviderProps) {
  const router = useRouter();
  const [modeId, setModeId] = useState<ResearchModeId>(
    initialMode && isResearchModeId(initialMode) ? initialMode : DEFAULT_MODE_ID,
  );
  const hasUserInteracted = useRef(false);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? localStorage.getItem(MODE_STORAGE_KEY) : null;
    if (stored && isResearchModeId(stored) && stored !== modeId) {
      setModeId(stored);
    }
  }, [modeId]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    localStorage.setItem(MODE_STORAGE_KEY, modeId);
    const maxAge = 60 * 60 * 24 * 365;
    document.cookie = `${MODE_COOKIE_KEY}=${modeId}; Path=/; Max-Age=${maxAge}; SameSite=Lax`;
    if (hasUserInteracted.current) {
      router.refresh();
    }
  }, [modeId, router]);

  const setMode = useCallback(
    (next: ResearchModeId) => {
      if (next === modeId) {
        return;
      }
      hasUserInteracted.current = true;
      setModeId(next);
    },
    [modeId],
  );

  const value = useMemo<ModeContextValue>(
    () => ({ mode: RESEARCH_MODES[modeId], setMode, modes: Object.values(RESEARCH_MODES) }),
    [modeId, setMode],
  );

  return <ModeContext.Provider value={value}>{children}</ModeContext.Provider>;
}

export function useMode(): ModeContextValue {
  const context = useContext(ModeContext);
  if (!context) {
    throw new Error("useMode must be used within a ModeProvider");
  }
  return context;
}

export function ModeSwitcher(): JSX.Element {
  const { mode, modes, setMode } = useMode();

  return (
    <div
      aria-live="polite"
      style={{
        display: "grid",
        gap: "0.5rem",
        padding: "0.75rem 1rem",
        borderRadius: "0.75rem",
        background: "rgba(15, 23, 42, 0.05)",
        border: "1px solid rgba(148, 163, 184, 0.4)",
        maxWidth: "28rem",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.75rem" }}>
        <label htmlFor="mode-selector" style={{ fontWeight: 600 }}>
          Research mode
        </label>
        <select
          id="mode-selector"
          value={mode.id}
          onChange={(event) => setMode(event.target.value as ResearchModeId)}
          style={{
            padding: "0.35rem 0.5rem",
            borderRadius: "0.5rem",
            border: "1px solid var(--border, #e5e7eb)",
            fontSize: "0.95rem",
          }}
        >
          {modes.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
      <p style={{ margin: 0, fontSize: "0.9rem", color: "var(--muted-foreground, #4b5563)" }}>{mode.description}</p>
      <dl
        style={{
          display: "grid",
          gap: "0.25rem",
          margin: 0,
          fontSize: "0.85rem",
          color: "var(--muted-foreground, #4b5563)",
        }}
      >
        <div style={{ display: "grid", gap: "0.25rem" }}>
          <dt style={{ fontWeight: 600 }}>Emphasises</dt>
          <dd style={{ margin: 0 }}>{mode.emphasis.join(", ")}</dd>
        </div>
        <div style={{ display: "grid", gap: "0.25rem" }}>
          <dt style={{ fontWeight: 600 }}>Softens</dt>
          <dd style={{ margin: 0 }}>{mode.suppressions.join(", ")}</dd>
        </div>
      </dl>
      <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--muted-foreground, #64748b)" }}>
        {formatEmphasisSummary(mode)}
      </p>
    </div>
  );
}
