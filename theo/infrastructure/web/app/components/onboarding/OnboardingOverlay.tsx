"use client";

import { OnboardingWizard } from "./OnboardingWizard";
import { useOnboardingState } from "../../lib/useOnboardingState";

export function OnboardingOverlay(): JSX.Element | null {
  const { shouldShow, hasAuthIssue, complete, dismiss } = useOnboardingState();

  if (!shouldShow) {
    return null;
  }

  return (
    <OnboardingWizard
      open={shouldShow}
      hasAuthIssue={hasAuthIssue}
      onDismiss={dismiss}
      onComplete={complete}
    />
  );
}
