import { useMemo, useState, type Dispatch, type SetStateAction } from "react";

import type { GuardrailSuggestion } from "../components/types";
import type { CopilotResult, WorkflowId } from "../components/types";
import type { ResearchFeatureFlags } from "../research/types";

export type CopilotWorkflowError = {
  message: string;
  suggestions?: GuardrailSuggestion[];
} | null;

export type CopilotWorkflowState = {
  enabled: boolean | null;
  workflow: WorkflowId;
  result: CopilotResult | null;
  isRunning: boolean;
  error: CopilotWorkflowError;
  citationExportStatus: string | null;
  isSendingCitations: boolean;
  researchFeatures: ResearchFeatureFlags | null;
  researchFeaturesError: string | null;
  activeTool: { id: string; osis?: string | null } | null;
  drawerOsis: string;
};

export type CopilotWorkflowSetters = {
  setEnabled: Dispatch<SetStateAction<boolean | null>>;
  setWorkflow: Dispatch<SetStateAction<WorkflowId>>;
  setResult: Dispatch<SetStateAction<CopilotResult | null>>;
  setIsRunning: Dispatch<SetStateAction<boolean>>;
  setError: Dispatch<SetStateAction<CopilotWorkflowError>>;
  setCitationExportStatus: Dispatch<SetStateAction<string | null>>;
  setIsSendingCitations: Dispatch<SetStateAction<boolean>>;
  setResearchFeatures: Dispatch<SetStateAction<ResearchFeatureFlags | null>>;
  setResearchFeaturesError: Dispatch<SetStateAction<string | null>>;
  setActiveTool: Dispatch<SetStateAction<{ id: string; osis?: string | null } | null>>;
  setDrawerOsis: Dispatch<SetStateAction<string>>;
};

export type CopilotWorkflowSelectors = {
  hasResult: boolean;
  canExportCitations: boolean;
};

export type UseCopilotWorkflowStateResult = {
  state: CopilotWorkflowState;
  setters: CopilotWorkflowSetters;
  selectors: CopilotWorkflowSelectors;
};

export function useCopilotWorkflowState(
  initialWorkflow: WorkflowId = "verse",
): UseCopilotWorkflowStateResult {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [workflow, setWorkflow] = useState<WorkflowId>(initialWorkflow);
  const [result, setResult] = useState<CopilotResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<CopilotWorkflowError>(null);
  const [citationExportStatus, setCitationExportStatus] = useState<string | null>(null);
  const [isSendingCitations, setIsSendingCitations] = useState(false);
  const [researchFeatures, setResearchFeatures] = useState<ResearchFeatureFlags | null>(null);
  const [researchFeaturesError, setResearchFeaturesError] = useState<string | null>(null);
  const [activeTool, setActiveTool] = useState<{ id: string; osis?: string | null } | null>(null);
  const [drawerOsis, setDrawerOsis] = useState("");

  const hasResult = useMemo(() => result !== null, [result]);
  const canExportCitations = useMemo(() => {
    if (!result) {
      return false;
    }
    switch (result.kind) {
      case "verse":
      case "sermon":
      case "comparative":
      case "multimedia":
      case "devotional":
      case "collaboration":
        return Boolean(result.payload.answer?.citations?.length);
      default:
        return false;
    }
  }, [result]);

  return {
    state: {
      enabled,
      workflow,
      result,
      isRunning,
      error,
      citationExportStatus,
      isSendingCitations,
      researchFeatures,
      researchFeaturesError,
      activeTool,
      drawerOsis,
    },
    setters: {
      setEnabled,
      setWorkflow,
      setResult,
      setIsRunning,
      setError,
      setCitationExportStatus,
      setIsSendingCitations,
      setResearchFeatures,
      setResearchFeaturesError,
      setActiveTool,
      setDrawerOsis,
    },
    selectors: {
      hasResult,
      canExportCitations,
    },
  };
}
