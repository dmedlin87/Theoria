"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { NetworkError, TheoApiError, subscribeToHttpErrors } from "./http";

const ONBOARDING_COMPLETED_KEY = "theoria.onboarding.completed";
const ONBOARDING_FIRST_VISIT_KEY = "theoria.onboarding.first-visit";
const ERROR_WINDOW_MS = 5 * 60 * 1000;

type OnboardingState = {
  /** Whether the onboarding wizard should currently be visible. */
  shouldShow: boolean;
  /** Indicates the wizard is being shown because the user is brand new. */
  isFirstVisit: boolean;
  /** True when we recently saw auth-related API failures. */
  hasAuthIssue: boolean;
  /** Mark onboarding as complete, hiding it permanently. */
  complete: () => void;
  /** Dismiss onboarding temporarily without marking completion. */
  dismiss: () => void;
};

export function useOnboardingState(): OnboardingState {
  const [isReady, setIsReady] = useState(false);
  const [hasCompleted, setHasCompleted] = useState(false);
  const [isFirstVisit, setIsFirstVisit] = useState(false);
  const [isDismissed, setIsDismissed] = useState(false);
  const [errorTimestamps, setErrorTimestamps] = useState<number[]>([]);
  const errorHistoryRef = useRef<number[]>([]);

  const pruneErrors = useCallback(() => {
    const now = Date.now();
    const filtered = errorHistoryRef.current.filter((timestamp) => now - timestamp < ERROR_WINDOW_MS);
    if (filtered.length !== errorHistoryRef.current.length) {
      errorHistoryRef.current = filtered;
      setErrorTimestamps(filtered);
    }
    return filtered;
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const completed = window.localStorage.getItem(ONBOARDING_COMPLETED_KEY) === "1";
    setHasCompleted(completed);

    const firstVisitRecorded = window.localStorage.getItem(ONBOARDING_FIRST_VISIT_KEY);
    if (!firstVisitRecorded) {
      window.localStorage.setItem(ONBOARDING_FIRST_VISIT_KEY, new Date().toISOString());
      setIsFirstVisit(true);
    }

    setIsReady(true);

    const handleStorage = (event: StorageEvent) => {
      if (event.key === ONBOARDING_COMPLETED_KEY) {
        setHasCompleted(event.newValue === "1");
      }
    };

    window.addEventListener("storage", handleStorage);

    return () => {
      window.removeEventListener("storage", handleStorage);
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const unsubscribe = subscribeToHttpErrors((error) => {
      if (error instanceof TheoApiError) {
        if (error.status !== 401 && error.status !== 403) {
          return;
        }
      } else if (!(error instanceof NetworkError)) {
        return;
      }

      const now = Date.now();
      const pruned = pruneErrors();
      const updated = [...pruned, now];
      errorHistoryRef.current = updated;
      setErrorTimestamps(updated);
      setIsDismissed(false);
    });

    return unsubscribe;
  }, [pruneErrors]);

  useEffect(() => {
    if (errorTimestamps.length === 0) {
      return;
    }
    const now = Date.now();
    const oldest = errorTimestamps[0];
    const timeout = window.setTimeout(() => {
      pruneErrors();
    }, Math.max(0, ERROR_WINDOW_MS - (now - oldest)));

    return () => {
      window.clearTimeout(timeout);
    };
  }, [errorTimestamps, pruneErrors]);

  const hasAuthIssue = useMemo(() => errorTimestamps.length > 0, [errorTimestamps]);

  const complete = useCallback(() => {
    setHasCompleted(true);
    setIsFirstVisit(false);
    setIsDismissed(false);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(ONBOARDING_COMPLETED_KEY, "1");
    }
  }, []);

  const dismiss = useCallback(() => {
    setIsFirstVisit(false);
    setIsDismissed(true);
    errorHistoryRef.current = [];
    setErrorTimestamps([]);
  }, []);

  const shouldShow = isReady && !hasCompleted && !isDismissed && (isFirstVisit || hasAuthIssue);

  return {
    shouldShow,
    isFirstVisit,
    hasAuthIssue,
    complete,
    dismiss,
  };
}
