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
  formatEmphasisSummary,
  isResearchModeId,
} from "./mode-config";
import {
  Popover,
  PopoverArrow,
  PopoverContent,
  PopoverTrigger,
} from "./components/ui/popover";

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
  const [popoverOpen, setPopoverOpen] = useState(false);
  const popoverContentId = useId();
  const popoverTitleId = `${popoverContentId}-title`;

  return (
    <div className="mode-switcher-compact" aria-live="polite">
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
        <Popover open={popoverOpen} onOpenChange={setPopoverOpen}>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="mode-switcher-compact__info"
              aria-label="Show mode information"
              aria-expanded={popoverOpen}
              aria-controls={popoverContentId}
              aria-haspopup="dialog"
              aria-describedby={popoverOpen ? popoverContentId : undefined}
              title="Learn about research modes"
            >
              ?
            </button>
          </PopoverTrigger>
          <PopoverContent
            id={popoverContentId}
            className="mode-switcher-compact__tooltip"
            align="end"
            aria-labelledby={popoverTitleId}
          >
            <div className="mode-switcher-compact__tooltip-header">
              <h4 id={popoverTitleId} className="mode-switcher-compact__tooltip-title">
                {mode.label} mode
              </h4>
              <button
                type="button"
                className="mode-switcher-compact__tooltip-close"
                onClick={() => setPopoverOpen(false)}
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
            <PopoverArrow />
          </PopoverContent>
        </Popover>
      </div>
      <p className="mode-switcher-compact__summary">
        {mode.label} — {getModeSummary(mode)}
      </p>
    </div>
  );
}
