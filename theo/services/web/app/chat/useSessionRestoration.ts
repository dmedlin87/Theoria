import { useEffect, useRef } from "react";
import type { ChatWorkflowClient } from "../lib/chat-client";
import type { ChatWorkspaceDispatch, ConversationEntry } from "./useChatWorkspaceState";

const CHAT_SESSION_STORAGE_KEY = "theo.chat.lastSessionId";
const RETRY_DELAYS = [1000, 2000, 4000]; // Exponential backoff

function createMessageId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2, 10);
}

export function useSessionRestoration(
  clientRef: React.RefObject<ChatWorkflowClient>,
  dispatch: ChatWorkspaceDispatch,
  restorationAttempts: number,
  canRetry: boolean
) {
  const isRestoringRef = useRef(false);
  const retryTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    // Cleanup on unmount
    return () => {
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
        retryTimeoutRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      dispatch({ type: "RESTORATION_COMPLETE" });
      return;
    }

    // Only run once on mount or when explicitly retrying
    if (isRestoringRef.current) {
      return;
    }

    const storedId = window.localStorage.getItem(CHAT_SESSION_STORAGE_KEY);
    if (!storedId) {
      dispatch({ type: "RESTORATION_COMPLETE" });
      return;
    }

    let cancelled = false;
    isRestoringRef.current = true;

    const restoreSession = async () => {
      try {
        dispatch({ type: "START_RESTORATION" });

        if (!clientRef.current) {
          throw new Error("Chat client not initialized");
        }

        const state = await clientRef.current.fetchChatSession(storedId);

        if (cancelled) {
          return;
        }

        if (!state) {
          window.localStorage.removeItem(CHAT_SESSION_STORAGE_KEY);
          dispatch({ type: "RESTORATION_COMPLETE" });
          return;
        }

        // Validate session data
        if (!state.sessionId) {
          throw new Error("Invalid session data: missing session ID");
        }

        // Reconstruct conversation
        const restoredConversation: ConversationEntry[] = [];
        if (state.memory && Array.isArray(state.memory)) {
          state.memory.forEach((entry) => {
            if (!entry.question || !entry.answer) {
              return; // Skip invalid entries
            }

            restoredConversation.push({
              id: createMessageId(),
              role: "user",
              content: entry.question,
            });

            restoredConversation.push({
              id: createMessageId(),
              role: "assistant",
              content: entry.answer,
              citations: entry.citations ?? [],
              prompt: entry.question,
            });
          });
        }

        // Find last question
        let lastQuestion: string | null = null;
        if (restoredConversation.length > 0) {
          const lastUser = restoredConversation
            .slice()
            .reverse()
            .find((entry) => entry.role === "user");
          lastQuestion = lastUser?.content ?? null;
        }

        dispatch({
          type: "RESTORATION_SUCCESS",
          payload: {
            sessionId: state.sessionId,
            conversation: restoredConversation,
            frequentlyOpenedPanels: state.preferences?.frequentlyOpenedPanels ?? [],
            defaultFilters: state.preferences?.defaultFilters ?? null,
            lastQuestion,
          },
        });
      } catch (error) {
        if (cancelled) {
          return;
        }

        const errorMessage = error instanceof Error
          ? error.message
          : "Failed to restore session";

        console.warn("Session restoration failed:", error);
        dispatch({ type: "RESTORATION_ERROR", error: errorMessage });

        // Attempt retry with exponential backoff
        if (canRetry && restorationAttempts < RETRY_DELAYS.length) {
          const delay = RETRY_DELAYS[restorationAttempts];
          console.log(`Retrying session restoration in ${delay}ms (attempt ${restorationAttempts + 1})`);

          retryTimeoutRef.current = setTimeout(() => {
            if (!cancelled) {
              dispatch({ type: "RESTORATION_RETRY" });
              isRestoringRef.current = false; // Allow retry
            }
          }, delay);
        } else {
          // Max retries exceeded, clear stored session
          window.localStorage.removeItem(CHAT_SESSION_STORAGE_KEY);
          dispatch({ type: "RESTORATION_COMPLETE" });
        }
      } finally {
        if (!cancelled && !canRetry) {
          isRestoringRef.current = false;
        }
      }
    };

    restoreSession();

    return () => {
      cancelled = true;
      isRestoringRef.current = false;
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
        retryTimeoutRef.current = null;
      }
    };
  }, [clientRef, dispatch, restorationAttempts, canRetry]);
}

export function useSessionPersistence(sessionId: string | null) {
  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    if (sessionId) {
      window.localStorage.setItem(CHAT_SESSION_STORAGE_KEY, sessionId);
    } else {
      window.localStorage.removeItem(CHAT_SESSION_STORAGE_KEY);
    }
  }, [sessionId]);
}

export { CHAT_SESSION_STORAGE_KEY };
