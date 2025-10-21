import { useMemo, useState, type Dispatch, type SetStateAction } from "react";

import type { ResearchPlan } from "../../lib/api-client";

import type {
  AssistantConversationEntry,
  ConversationEntry,
  GuardrailState,
  Reaction,
} from "../useChatWorkspaceState";
import type { HybridSearchFilters } from "../../lib/api-client";
import type { InterpretedApiError } from "../../lib/errorMessages";

export type ChatSessionState = {
  conversation: ConversationEntry[];
  feedbackSelections: Partial<Record<string, Reaction>>;
  pendingFeedbackIds: Set<string>;
  sessionId: string | null;
  isRestoring: boolean;
  frequentlyOpenedPanels: string[];
  defaultFilters: HybridSearchFilters | null;
  isStreaming: boolean;
  activeAssistantId: string | null;
  guardrail: GuardrailState;
  errorMessage: InterpretedApiError | null;
  lastQuestion: string | null;
  plan: ResearchPlan | null;
};

export type ChatSessionSetters = {
  setConversation: Dispatch<SetStateAction<ConversationEntry[]>>;
  setFeedbackSelections: Dispatch<SetStateAction<Partial<Record<string, Reaction>>>>;
  setPendingFeedbackIds: Dispatch<SetStateAction<Set<string>>>;
  setSessionId: Dispatch<SetStateAction<string | null>>;
  setIsRestoring: Dispatch<SetStateAction<boolean>>;
  setFrequentlyOpenedPanels: Dispatch<SetStateAction<string[]>>;
  setDefaultFilters: Dispatch<SetStateAction<HybridSearchFilters | null>>;
  setIsStreaming: Dispatch<SetStateAction<boolean>>;
  setActiveAssistantId: Dispatch<SetStateAction<string | null>>;
  setGuardrail: Dispatch<SetStateAction<GuardrailState>>;
  setErrorMessage: Dispatch<SetStateAction<InterpretedApiError | null>>;
  setLastQuestion: Dispatch<SetStateAction<string | null>>;
  setPlan: Dispatch<SetStateAction<ResearchPlan | null>>;
};

export type ChatSessionSelectors = {
  hasTranscript: boolean;
  activeAssistantEntry: AssistantConversationEntry | null;
};

export type UseChatSessionStateResult = {
  state: ChatSessionState;
  setters: ChatSessionSetters;
  selectors: ChatSessionSelectors;
};

export function useChatSessionState(): UseChatSessionStateResult {
  const [conversation, setConversation] = useState<ConversationEntry[]>([]);
  const [feedbackSelections, setFeedbackSelections] = useState<
    Partial<Record<string, Reaction>>
  >({});
  const [pendingFeedbackIds, setPendingFeedbackIds] = useState<Set<string>>(
    () => new Set(),
  );
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isRestoring, setIsRestoring] = useState(true);
  const [frequentlyOpenedPanels, setFrequentlyOpenedPanels] = useState<string[]>([]);
  const [defaultFilters, setDefaultFilters] = useState<HybridSearchFilters | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeAssistantId, setActiveAssistantId] = useState<string | null>(null);
  const [guardrail, setGuardrail] = useState<GuardrailState>(null);
  const [errorMessage, setErrorMessage] = useState<InterpretedApiError | null>(null);
  const [lastQuestion, setLastQuestion] = useState<string | null>(null);
  const [plan, setPlan] = useState<ResearchPlan | null>(null);

  const hasTranscript = useMemo(() => conversation.length > 0, [conversation]);
  const activeAssistantEntry = useMemo(() => {
    if (!activeAssistantId) {
      return null;
    }
    const candidate = conversation.find(
      (entry): entry is AssistantConversationEntry =>
        entry.role === "assistant" && entry.id === activeAssistantId,
    );
    return candidate ?? null;
  }, [activeAssistantId, conversation]);

  return {
    state: {
      conversation,
      feedbackSelections,
      pendingFeedbackIds,
      sessionId,
      isRestoring,
      frequentlyOpenedPanels,
      defaultFilters,
      isStreaming,
      activeAssistantId,
      guardrail,
      errorMessage,
      lastQuestion,
      plan,
    },
    setters: {
      setConversation,
      setFeedbackSelections,
      setPendingFeedbackIds,
      setSessionId,
      setIsRestoring,
      setFrequentlyOpenedPanels,
      setDefaultFilters,
      setIsStreaming,
      setActiveAssistantId,
      setGuardrail,
      setErrorMessage,
      setLastQuestion,
      setPlan,
    },
    selectors: {
      hasTranscript,
      activeAssistantEntry,
    },
  };
}
