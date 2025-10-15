"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";

import { FocusTrapRegion } from "../a11y/FocusTrapRegion";
import { emitTelemetry } from "../../lib/telemetry";

import styles from "./OnboardingWizard.module.css";

type WizardStepId = "welcome" | "api" | "tour" | "complete";

type WizardStep = {
  id: WizardStepId;
  title: string;
  subtitle: string;
};

const STEPS: WizardStep[] = [
  {
    id: "welcome",
    title: "Welcome to Theoria",
    subtitle: "Let's get your workspace configured in under two minutes.",
  },
  {
    id: "api",
    title: "Connect your API credentials",
    subtitle: "Configure access so Theoria can reach your preferred language models.",
  },
  {
    id: "tour",
    title: "Explore what you can do",
    subtitle: "A quick tour of the research workflows available in the workspace.",
  },
  {
    id: "complete",
    title: "You're all set",
    subtitle: "Jump into the workspace with confidence—everything is ready.",
  },
];

const ENV_COMMAND = `export THEORIA_API_KEY="<your-api-key>"
export THEORIA_API_BASE="https://api.theoria.app"`;

interface OnboardingWizardProps {
  open: boolean;
  onNext?: (step: WizardStepId) => void;
  onBack?: (step: WizardStepId) => void;
  onDismiss: () => void;
  onComplete: () => void;
  hasAuthIssue?: boolean;
}

export function OnboardingWizard({
  open,
  onNext,
  onBack,
  onDismiss,
  onComplete,
  hasAuthIssue = false,
}: OnboardingWizardProps) {
  const [isMounted, setIsMounted] = useState(false);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle");

  const step = STEPS[currentStepIndex];
  const isLastStep = currentStepIndex === STEPS.length - 1;

  useEffect(() => {
    setIsMounted(true);
  }, []);

  useEffect(() => {
    if (!open) {
      setCurrentStepIndex(0);
      setCopyState("idle");
      if (typeof document !== "undefined") {
        document.body.style.overflow = "";
      }
      return;
    }

    if (typeof document !== "undefined") {
      document.body.style.overflow = "hidden";
    }

    void emitTelemetry(
      [
        {
          event: "onboarding.opened",
          durationMs: 0,
          metadata: { step: step.id },
        },
      ],
      { page: "onboarding" },
    );

    return () => {
      if (typeof document !== "undefined") {
        document.body.style.overflow = "";
      }
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const current = STEPS[currentStepIndex];
    void emitTelemetry(
      [
        {
          event: "onboarding.step_view",
          durationMs: 0,
          metadata: { step: current.id },
        },
      ],
      { page: "onboarding" },
    );
  }, [open, currentStepIndex]);

  const handleNext = () => {
    const current = STEPS[currentStepIndex];
    if (isLastStep) {
      void emitTelemetry(
        [
          {
            event: "onboarding.completed",
            durationMs: 0,
            metadata: { step: current.id },
          },
        ],
        { page: "onboarding" },
      );
      onComplete();
      return;
    }

    void emitTelemetry(
      [
        {
          event: "onboarding.step_advance",
          durationMs: 0,
          metadata: { from: current.id, to: STEPS[currentStepIndex + 1].id },
        },
      ],
      { page: "onboarding" },
    );
    onNext?.(current.id);
    setCurrentStepIndex((index) => Math.min(index + 1, STEPS.length - 1));
  };

  const handleBack = () => {
    if (currentStepIndex === 0) {
      return;
    }
    const previous = STEPS[currentStepIndex - 1];
    void emitTelemetry(
      [
        {
          event: "onboarding.step_back",
          durationMs: 0,
          metadata: { from: step.id, to: previous.id },
        },
      ],
      { page: "onboarding" },
    );
    onBack?.(step.id);
    setCurrentStepIndex((index) => Math.max(index - 1, 0));
  };

  const handleDismiss = () => {
    void emitTelemetry(
      [
        {
          event: "onboarding.dismissed",
          durationMs: 0,
          metadata: { step: step.id },
        },
      ],
      { page: "onboarding" },
    );
    onDismiss();
  };

  const handleCopy = async () => {
    if (!navigator?.clipboard?.writeText) {
      setCopyState("error");
      return;
    }
    try {
      await navigator.clipboard.writeText(ENV_COMMAND);
      setCopyState("copied");
      void emitTelemetry(
        [
          {
            event: "onboarding.copy_env",
            durationMs: 0,
          },
        ],
        { page: "onboarding" },
      );
    } catch (error) {
      if (process.env.NODE_ENV !== "production") {
        console.warn("Failed to copy onboarding env command", error);
      }
      setCopyState("error");
    }
  };

  const apiSupportNote = useMemo(() => {
    if (!hasAuthIssue) {
      return null;
    }
    return (
      <p className={styles.highlight} data-testid="auth-issue-note">
        We noticed recent authentication errors. Double-check your API key and ensure your
        settings reflect the correct workspace region.
      </p>
    );
  }, [hasAuthIssue]);

  if (!open || !isMounted) {
    return null;
  }

  const portalContent = (
    <div className={styles.overlay} role="presentation">
      <FocusTrapRegion
        active={open}
        fallbackFocus={() => document.body}
        initialFocus={() => document.querySelector("[data-onboarding-focus]") ?? document.body}
      >
        <section
          role="dialog"
          aria-modal="true"
          aria-labelledby="onboarding-wizard-title"
          className={styles.panel}
        >
          <div className={styles.header}>
            <span className={styles.badge}>Getting started</span>
            <h2 id="onboarding-wizard-title" className={styles.title}>
              {step.title}
            </h2>
            <p className={styles.subtitle}>{step.subtitle}</p>
          </div>

          <div className={styles.steps} aria-hidden="true">
            {STEPS.map((wizardStep) => (
              <span
                key={wizardStep.id}
                className={styles.stepDot}
                data-active={wizardStep.id === step.id}
              />
            ))}
          </div>

          <div className={styles.body}>{renderStepContent(step.id, apiSupportNote, copyState, handleCopy)}</div>

          <div className={styles.actions}>
            <button type="button" className={styles.ghostButton} onClick={handleDismiss}>
              Skip for now
            </button>
            <div style={{ display: "flex", gap: "0.75rem" }}>
              <button
                type="button"
                className={styles.secondaryButton}
                onClick={handleBack}
                disabled={currentStepIndex === 0}
              >
                Back
              </button>
              <button
                type="button"
                className={styles.primaryButton}
                onClick={handleNext}
                data-onboarding-focus
              >
                {isLastStep ? "Finish" : "Next"}
              </button>
            </div>
          </div>
        </section>
      </FocusTrapRegion>
    </div>
  );

  return createPortal(portalContent, document.body);
}

function renderStepContent(
  step: WizardStepId,
  apiSupportNote: JSX.Element | null,
  copyState: "idle" | "copied" | "error",
  onCopy: () => void,
): JSX.Element {
  switch (step) {
    case "welcome":
      return (
        <div>
          <p>
            Theoria unifies research chat, semantic search, and manuscript exploration. We'll walk
            through connecting your APIs and highlight what's possible.
          </p>
          <ul className={styles.list}>
            <li>Stream AI-assisted chat grounded in your curated corpora.</li>
            <li>Search across manuscripts, commentaries, and notes instantly.</li>
            <li>Build guardrails so your assistants stay aligned with doctrine.</li>
          </ul>
        </div>
      );
    case "api":
      return (
        <div>
          <p>
            Head to the <Link href="/settings">Settings</Link> page to add your provider keys. For
            hosted deployments you can use the following environment snippet:
          </p>
          {apiSupportNote}
          <div className={styles.commandBlock}>
            <button type="button" onClick={onCopy} className={styles.copyButton}>
              {copyState === "copied" ? "Copied" : "Copy"}
            </button>
            <code className={styles.commandText}>{ENV_COMMAND}</code>
          </div>
          <p>
            Need help? Reach out to <a href="mailto:support@theoria.app">support@theoria.app</a>.
          </p>
        </div>
      );
    case "tour":
      return (
        <div>
          <div className={styles.highlight}>
            <strong>Workspace highlights</strong>
            <ul className={styles.list}>
              <li>
                <strong>Chat studio:</strong> orchestrate retrieval-augmented chat with guardrails and
                cite sources instantly.
              </li>
              <li>
                <strong>Search:</strong> filter manuscripts, sermons, and translations with structured
                facets.
              </li>
              <li>
                <strong>Verse explorer:</strong> jump to any OSIS reference to compare commentaries and
                manuscripts side-by-side.
              </li>
            </ul>
          </div>
          <p>
            As you explore, the command palette (<kbd>⌘</kbd> / <kbd>Ctrl</kbd> + <kbd>K</kbd>) surfaces
            shortcuts to every tool.
          </p>
        </div>
      );
    case "complete":
      return (
        <div>
          <p>
            You're ready to dive in. Start a chat, run a search, or upload new corpora—your workspace is
            configured.
          </p>
          <p>
            We love feedback. Share ideas anytime via the feedback widget or email us at
            support@theoria.app.
          </p>
        </div>
      );
    default:
      return <></>;
  }
}
