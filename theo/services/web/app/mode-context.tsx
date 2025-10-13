"use client";

// Canonical research mode context for the web app. All consumers should import
// ModeProvider, useMode, and related helpers from this module rather than any
// legacy exports that previously lived under app/context/ModeContext.

import {
  type ReactNode,
  type FocusEvent,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
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
  const [modeId, setModeId] = useState<ResearchModeId>(() => {
    if (initialMode && isResearchModeId(initialMode)) {
      return initialMode;
    }
    if (typeof document === "undefined") {
      return DEFAULT_MODE_ID;
    }
    try {
      const stored =
        typeof window !== "undefined"
          ? window.localStorage.getItem(MODE_STORAGE_KEY)
          : null;
      if (stored && isResearchModeId(stored)) {
        return stored;
      }
      const cookiePrefix = `${MODE_COOKIE_KEY}=`;
      const cookieValue = document.cookie
        .split("; ")
        .find((entry) => entry.startsWith(cookiePrefix))
        ?.slice(cookiePrefix.length);
      if (cookieValue && isResearchModeId(cookieValue)) {
        return cookieValue;
      }
    } catch {
      // Ignore persistence errors
    }
    return DEFAULT_MODE_ID;
  });
  const hasUserInteracted = useRef(false);
  const hasHydratedRef = useRef(typeof window === "undefined");

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    hasHydratedRef.current = true;
  }, []);

  useEffect(() => {
    if (typeof window === "undefined" || !hasHydratedRef.current) {
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

function getModeSummary(mode: ResearchMode): string {
  const summaries: Record<ResearchModeId, string> = {
    balanced: "Blends critical & devotional perspectives",
    investigative: "Surfaces variants, tensions & critical questions",
    devotional: "Emphasizes pastoral insights & application",
  };
  return summaries[mode.id];
}

export function ModeSwitcher(): JSX.Element {
  const { mode, modes, setMode } = useMode();
  const [showTooltip, setShowTooltip] = useState(false);
  const tooltipWrapperRef = useRef<HTMLDivElement>(null);
  const tooltipId = useId();

  const handleFocusOut = useCallback(
    (event: FocusEvent<HTMLDivElement>) => {
      const nextFocused = event.relatedTarget as Node | null;
      if (!tooltipWrapperRef.current?.contains(nextFocused)) {
        setShowTooltip(false);
      }
    },
    [],
  );

  useEffect(() => {
    if (!showTooltip) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      if (!tooltipWrapperRef.current?.contains(event.target as Node)) {
        setShowTooltip(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setShowTooltip(false);
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [showTooltip]);

  return (
    <div
      className="mode-switcher-compact"
      aria-live="polite"
      ref={tooltipWrapperRef}
      onBlurCapture={handleFocusOut}
    >
      <div className="mode-switcher-compact__control">
        <label htmlFor="mode-selector" className="mode-switcher-compact__label">
          Mode
        </label>
        <select
          id="mode-selector"
          value={mode.id}
          onChange={(event) => setMode(event.target.value as ResearchModeId)}
          className="mode-switcher-compact__select"
          title={mode.description}
        >
          {modes.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="mode-switcher-compact__info"
          onClick={() => setShowTooltip(!showTooltip)}
          aria-label="Show mode information"
          aria-expanded={showTooltip}
          aria-controls={tooltipId}
          aria-describedby={showTooltip ? tooltipId : undefined}
          title="Learn about research modes"
        >
          ?
        </button>
      </div>
      <p className="mode-switcher-compact__summary">
        {mode.label} — {getModeSummary(mode)}
      </p>
      {showTooltip && (
        <div
          className="mode-switcher-compact__tooltip"
          role="tooltip"
          id={tooltipId}
        >
          <div className="mode-switcher-compact__tooltip-header">
            <h4 className="mode-switcher-compact__tooltip-title">{mode.label} mode</h4>
            <button
              type="button"
              className="mode-switcher-compact__tooltip-close"
              onClick={() => setShowTooltip(false)}
              aria-label="Close"
            >
              ×
            </button>
          </div>
          <p className="mode-switcher-compact__tooltip-desc">{mode.description}</p>
          <dl className="mode-switcher-compact__tooltip-meta">
            <div className="mode-switcher-compact__tooltip-row">
              <dt>Emphasises</dt>
              <dd>{mode.emphasis.join(", ")}</dd>
            </div>
            <div className="mode-switcher-compact__tooltip-row">
              <dt>Softens</dt>
              <dd>{mode.suppressions.join(", ")}</dd>
            </div>
          </dl>
          <p className="mode-switcher-compact__tooltip-note">
            Choose the mode that best fits your task. Switching updates future answers accordingly.
          </p>
        </div>
      )}
    </div>
  );
}
