"use client";

// Canonical research mode context for the web app. All consumers should import
// ModeProvider, useMode, and related helpers from this module rather than any
// legacy exports that previously lived under app/context/ModeContext.

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
  const [hasHydrated, setHasHydrated] = useState(false);

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }

    let persisted: ResearchModeId | undefined;

    try {
      const stored =
        typeof window !== "undefined"
          ? window.localStorage.getItem(MODE_STORAGE_KEY)
          : null;

      if (stored && isResearchModeId(stored)) {
        persisted = stored;
      } else {
        const cookiePrefix = `${MODE_COOKIE_KEY}=`;
        const cookieValue = document.cookie
          .split("; ")
          .find((entry) => entry.startsWith(cookiePrefix))
          ?.slice(cookiePrefix.length);

        if (cookieValue && isResearchModeId(cookieValue)) {
          persisted = cookieValue;
        }
      }
    } catch {
      persisted = undefined;
    }

    if (persisted) {
      setModeId((current) => (current === persisted ? current : persisted));
    }

    setHasHydrated(true);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined" || !hasHydrated) {
      return;
    }
    try {
      window.localStorage.setItem(MODE_STORAGE_KEY, modeId);
      const maxAge = 60 * 60 * 24 * 365;
      document.cookie = `${MODE_COOKIE_KEY}=${modeId}; Path=/; Max-Age=${maxAge}; SameSite=Lax`;
    } catch {
      return;
    }
    if (hasUserInteracted.current) {
      router.refresh();
    }
  }, [hasHydrated, modeId, router]);

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
  const [showAdvanced, setShowAdvanced] = useState(false);

  if (!showAdvanced) {
    return (
      <div className="mode-panel mode-panel--compact" aria-live="polite">
        <p className="mode-panel__summary">{formatEmphasisSummary(mode)}</p>
        <p className="mode-panel__help">
          Switch modes when you need results to lean more scholarly or devotional—changing the
          mode refreshes search and chat responses to match.
        </p>
        <button
          type="button"
          className="mode-panel__button"
          onClick={() => setShowAdvanced(true)}
        >
          Change mode
        </button>
      </div>
    );
  }

  return (
    <div className="mode-panel" aria-live="polite">
      <div className="mode-panel__header">
        <label htmlFor="mode-selector" className="mode-panel__title">
          Research mode
        </label>
        <div className="mode-panel__control">
          <select
            id="mode-selector"
            value={mode.id}
            onChange={(event) => setMode(event.target.value as ResearchModeId)}
            className="mode-panel__select"
          >
            {modes.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      <p className="mode-panel__description">{mode.description}</p>
      <p className="mode-panel__help">
        Choose the mode that best fits your task. Investigative mode surfaces critical variants,
        while Devotional centres pastoral insight; switching updates future answers accordingly.
      </p>
      <details className="mode-panel__details">
        <summary className="mode-panel__details-summary">See emphasis and softening details</summary>
        <dl className="mode-panel__meta">
          <div className="mode-panel__row">
            <dt className="mode-panel__label">Emphasises</dt>
            <dd className="mode-panel__value">{mode.emphasis.join(", ")}</dd>
          </div>
          <div className="mode-panel__row">
            <dt className="mode-panel__label">Softens</dt>
            <dd className="mode-panel__value">{mode.suppressions.join(", ")}</dd>
          </div>
        </dl>
      </details>
      <p className="mode-panel__summary">{formatEmphasisSummary(mode)}</p>
      <button
        type="button"
        className="mode-panel__button mode-panel__button--secondary"
        onClick={() => setShowAdvanced(false)}
      >
        Done
      </button>
    </div>
  );
}
