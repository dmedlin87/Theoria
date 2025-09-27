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
  const [hasHydrated, setHasHydrated] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || hasHydrated) {
      return;
    }
    const stored = localStorage.getItem(MODE_STORAGE_KEY);
    if (stored && isResearchModeId(stored) && stored !== modeId) {
      setModeId(stored);
    }
    setHasHydrated(true);
  }, [hasHydrated, modeId]);

  useEffect(() => {
    if (typeof window === "undefined" || !hasHydrated) {
      return;
    }
    localStorage.setItem(MODE_STORAGE_KEY, modeId);
    const maxAge = 60 * 60 * 24 * 365;
    document.cookie = `${MODE_COOKIE_KEY}=${modeId}; Path=/; Max-Age=${maxAge}; SameSite=Lax`;
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
      <p className="mode-panel__summary">{formatEmphasisSummary(mode)}</p>
    </div>
  );
}
