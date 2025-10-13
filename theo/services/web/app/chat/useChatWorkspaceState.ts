import { useReducer, useCallback, Dispatch } from "react";
import type { RAGCitation } from "../copilot/components/types";
import type { HybridSearchFilters } from "../lib/guardrails";
import type { GuardrailFailureMetadata, GuardrailSuggestion } from "../lib/guardrails";

export type ConversationEntry =
  | { id: string; role: "user"; content: string }
  | {
      id: string;
      role: "assistant";
      content: string;
      citations: RAGCitation[];
      prompt?: string;
    };

export type AssistantConversationEntry = Extract<ConversationEntry, { role: "assistant" }>;

export type Reaction = "like" | "dislike";

export type GuardrailState = {
  message: string;
  traceId: string | null;
  suggestions: GuardrailSuggestion[];
  metadata: GuardrailFailureMetadata | null;
} | null;

export type SessionRestorationStatus = "idle" | "loading" | "success" | "error" | "retrying";

export type ChatWorkspaceState = {
  // Conversation
  conversation: ConversationEntry[];
  feedbackSelections: Partial<Record<string, Reaction>>;
  pendingFeedbackIds: Set<string>;
  
  // Session
  sessionId: string | null;
  isRestoring: boolean;
  restorationStatus: SessionRestorationStatus;
  restorationError: string | null;
  restorationAttempts: number;
  
  // Preferences
  frequentlyOpenedPanels: string[];
  defaultFilters: HybridSearchFilters | null;
  
  // Streaming
  isStreaming: boolean;
  activeAssistantId: string | null;
  
  // Errors
  guardrail: GuardrailState;
  errorMessage: string | null;
  lastQuestion: string | null;
};

export type ChatWorkspaceAction =
  | { type: "START_RESTORATION" }
  | { type: "RESTORATION_SUCCESS"; payload: {
      sessionId: string;
      conversation: ConversationEntry[];
      frequentlyOpenedPanels: string[];
      defaultFilters: HybridSearchFilters | null;
      lastQuestion: string | null;
    }}
  | { type: "RESTORATION_ERROR"; error: string }
  | { type: "RESTORATION_RETRY" }
  | { type: "RESTORATION_COMPLETE" }
  | { type: "START_STREAMING"; payload: {
      userEntry: ConversationEntry;
      assistantEntry: AssistantConversationEntry;
      question: string;
    }}
  | { type: "UPDATE_ASSISTANT_FRAGMENT"; assistantId: string; content: string }
  | { type: "UPDATE_ASSISTANT_COMPLETE"; assistantId: string; payload: {
      content: string;
      citations: RAGCitation[];
    }}
  | { type: "STREAMING_COMPLETE"; sessionId: string | null }
  | { type: "REMOVE_ENTRY"; entryId: string }
  | { type: "SET_GUARDRAIL"; guardrail: GuardrailState }
  | { type: "CLEAR_GUARDRAIL" }
  | { type: "SET_ERROR"; error: string | null }
  | { type: "SET_FEEDBACK_PENDING"; entryId: string; pending: boolean }
  | { type: "SET_FEEDBACK_SELECTION"; entryId: string; reaction: Reaction }
  | { type: "SET_SESSION_ID"; sessionId: string | null }
  | { type: "SET_PREFERENCES"; payload: {
      frequentlyOpenedPanels?: string[];
      defaultFilters?: HybridSearchFilters | null;
    }}
  | { type: "RESET_SESSION" }
  | { type: "FORK_SESSION" };

const MAX_RESTORATION_ATTEMPTS = 3;

function chatWorkspaceReducer(
  state: ChatWorkspaceState,
  action: ChatWorkspaceAction
): ChatWorkspaceState {
  switch (action.type) {
    case "START_RESTORATION":
      return {
        ...state,
        isRestoring: true,
        restorationStatus: "loading",
        restorationError: null,
      };

    case "RESTORATION_SUCCESS":
      return {
        ...state,
        isRestoring: false,
        restorationStatus: "success",
        restorationError: null,
        restorationAttempts: 0,
        sessionId: action.payload.sessionId,
        conversation: action.payload.conversation,
        frequentlyOpenedPanels: action.payload.frequentlyOpenedPanels,
        defaultFilters: action.payload.defaultFilters,
        lastQuestion: action.payload.lastQuestion,
        feedbackSelections: {},
        pendingFeedbackIds: new Set(),
      };

    case "RESTORATION_ERROR":
      return {
        ...state,
        restorationStatus: "error",
        restorationError: action.error,
        restorationAttempts: state.restorationAttempts + 1,
      };

    case "RESTORATION_RETRY":
      return {
        ...state,
        restorationStatus: "retrying",
        restorationError: null,
      };

    case "RESTORATION_COMPLETE":
      return {
        ...state,
        isRestoring: false,
        restorationStatus: state.restorationStatus === "error" ? "error" : "idle",
      };

    case "START_STREAMING": {
      const newConversation = [
        ...state.conversation,
        action.payload.userEntry,
        action.payload.assistantEntry,
      ];
      return {
        ...state,
        conversation: newConversation,
        activeAssistantId: action.payload.assistantEntry.id,
        isStreaming: true,
        guardrail: null,
        errorMessage: null,
        lastQuestion: action.payload.question,
      };
    }

    case "UPDATE_ASSISTANT_FRAGMENT": {
      const updatedConversation = state.conversation.map((entry) => {
        if (entry.id === action.assistantId && entry.role === "assistant") {
          return {
            ...entry,
            content: entry.content + action.content,
          };
        }
        return entry;
      });
      return {
        ...state,
        conversation: updatedConversation,
      };
    }

    case "UPDATE_ASSISTANT_COMPLETE": {
      const updatedConversation = state.conversation.map((entry) => {
        if (entry.id === action.assistantId && entry.role === "assistant") {
          return {
            ...entry,
            content: action.payload.content,
            citations: action.payload.citations,
          };
        }
        return entry;
      });
      return {
        ...state,
        conversation: updatedConversation,
      };
    }

    case "STREAMING_COMPLETE":
      return {
        ...state,
        isStreaming: false,
        activeAssistantId: null,
        sessionId: action.sessionId ?? state.sessionId,
      };

    case "REMOVE_ENTRY": {
      const filteredConversation = state.conversation.filter(
        (entry) => entry.id !== action.entryId
      );
      const remainingFeedback = { ...state.feedbackSelections };
      delete remainingFeedback[action.entryId];
      const newPendingIds = new Set(state.pendingFeedbackIds);
      newPendingIds.delete(action.entryId);

      return {
        ...state,
        conversation: filteredConversation,
        feedbackSelections: remainingFeedback,
        pendingFeedbackIds: newPendingIds,
      };
    }

    case "SET_GUARDRAIL":
      return {
        ...state,
        guardrail: action.guardrail,
      };

    case "CLEAR_GUARDRAIL":
      return {
        ...state,
        guardrail: null,
      };

    case "SET_ERROR":
      return {
        ...state,
        errorMessage: action.error,
      };

    case "SET_FEEDBACK_PENDING": {
      const newPendingIds = new Set(state.pendingFeedbackIds);
      if (action.pending) {
        newPendingIds.add(action.entryId);
      } else {
        newPendingIds.delete(action.entryId);
      }
      return {
        ...state,
        pendingFeedbackIds: newPendingIds,
      };
    }

    case "SET_FEEDBACK_SELECTION":
      return {
        ...state,
        feedbackSelections: {
          ...state.feedbackSelections,
          [action.entryId]: action.reaction,
        },
      };

    case "SET_SESSION_ID":
      return {
        ...state,
        sessionId: action.sessionId,
      };

    case "SET_PREFERENCES":
      return {
        ...state,
        frequentlyOpenedPanels:
          action.payload.frequentlyOpenedPanels ?? state.frequentlyOpenedPanels,
        defaultFilters:
          action.payload.defaultFilters !== undefined
            ? action.payload.defaultFilters
            : state.defaultFilters,
      };

    case "RESET_SESSION":
      return {
        ...state,
        conversation: [],
        feedbackSelections: {},
        pendingFeedbackIds: new Set(),
        sessionId: null,
        guardrail: null,
        errorMessage: null,
        lastQuestion: null,
        isStreaming: false,
        activeAssistantId: null,
        defaultFilters: null,
        frequentlyOpenedPanels: [],
      };

    case "FORK_SESSION":
      return {
        ...state,
        sessionId: null,
      };

    default:
      return state;
  }
}

const initialState: ChatWorkspaceState = {
  conversation: [],
  feedbackSelections: {},
  pendingFeedbackIds: new Set(),
  sessionId: null,
  isRestoring: true,
  restorationStatus: "idle",
  restorationError: null,
  restorationAttempts: 0,
  frequentlyOpenedPanels: [],
  defaultFilters: null,
  isStreaming: false,
  activeAssistantId: null,
  guardrail: null,
  errorMessage: null,
  lastQuestion: null,
};

export function useChatWorkspaceState() {
  const [state, dispatch] = useReducer(chatWorkspaceReducer, initialState);

  const updateAssistantFragment = useCallback(
    (assistantId: string, content: string) => {
      dispatch({ type: "UPDATE_ASSISTANT_FRAGMENT", assistantId, content });
    },
    []
  );

  const updateAssistantComplete = useCallback(
    (assistantId: string, content: string, citations: RAGCitation[]) => {
      dispatch({
        type: "UPDATE_ASSISTANT_COMPLETE",
        assistantId,
        payload: { content, citations },
      });
    },
    []
  );

  const removeEntry = useCallback((entryId: string) => {
    dispatch({ type: "REMOVE_ENTRY", entryId });
  }, []);

  const setGuardrail = useCallback((guardrail: GuardrailState) => {
    dispatch({ type: "SET_GUARDRAIL", guardrail });
  }, []);

  const clearGuardrail = useCallback(() => {
    dispatch({ type: "CLEAR_GUARDRAIL" });
  }, []);

  const setError = useCallback((error: string | null) => {
    dispatch({ type: "SET_ERROR", error });
  }, []);

  const setFeedbackPending = useCallback((entryId: string, pending: boolean) => {
    dispatch({ type: "SET_FEEDBACK_PENDING", entryId, pending });
  }, []);

  const setFeedbackSelection = useCallback((entryId: string, reaction: Reaction) => {
    dispatch({ type: "SET_FEEDBACK_SELECTION", entryId, reaction });
  }, []);

  const canRetryRestoration = state.restorationAttempts < MAX_RESTORATION_ATTEMPTS;

  return {
    state,
    dispatch,
    actions: {
      updateAssistantFragment,
      updateAssistantComplete,
      removeEntry,
      setGuardrail,
      clearGuardrail,
      setError,
      setFeedbackPending,
      setFeedbackSelection,
    },
    computed: {
      hasTranscript: state.conversation.length > 0,
      canRetryRestoration,
    },
  };
}

export type ChatWorkspaceStateManager = ReturnType<typeof useChatWorkspaceState>;
export type ChatWorkspaceDispatch = Dispatch<ChatWorkspaceAction>;
