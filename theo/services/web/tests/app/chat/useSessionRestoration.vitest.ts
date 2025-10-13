import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  CHAT_SESSION_STORAGE_KEY,
  useSessionPersistence,
  useSessionRestoration,
} from "../../../app/chat/useSessionRestoration";
import type { ChatWorkflowClient } from "../../../app/lib/chat-client";
import type { ChatSessionState } from "../../../app/lib/api-client";
import type { ChatWorkspaceDispatch } from "../../../app/chat/useChatWorkspaceState";

describe("useSessionRestoration", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("restores a persisted chat session on mount", async () => {
    const dispatch: ChatWorkspaceDispatch = vi.fn();
    const client: ChatWorkflowClient = {
      runChatWorkflow: vi.fn(),
      fetchChatSession: vi.fn(async () => ({
        sessionId: "session-123",
        memory: [
          {
            question: "What does John 1 teach?",
            answer: "The prologue declares Jesus as the eternal Logos.",
            citations: [],
            documentIds: [],
            createdAt: "2024-01-01T00:00:00.000Z",
          },
        ],
        documentIds: [],
        createdAt: "2024-01-01T00:00:00.000Z",
        updatedAt: "2024-01-01T00:00:00.000Z",
        lastInteractionAt: "2024-01-01T00:00:00.000Z",
        preferences: {
          frequentlyOpenedPanels: ["citations"],
          defaultFilters: { collection: "sermons" },
        },
      })),
    };
    localStorage.setItem(CHAT_SESSION_STORAGE_KEY, "session-123");

    const { unmount } = renderHook(() =>
      useSessionRestoration({ current: client }, dispatch, 0, true)
    );

    await waitFor(() => {
      expect(dispatch).toHaveBeenCalledWith({ type: "START_RESTORATION" });
    });

    await waitFor(() => {
      expect(dispatch).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "RESTORATION_SUCCESS",
          payload: expect.objectContaining({
            sessionId: "session-123",
            conversation: expect.arrayContaining([
              expect.objectContaining({ role: "user" }),
              expect.objectContaining({ role: "assistant" }),
            ]),
            frequentlyOpenedPanels: ["citations"],
            defaultFilters: { collection: "sermons" },
            lastQuestion: "What does John 1 teach?",
          }),
        })
      );
    });

    unmount();
  });

  it("restores an empty session without transcript data", async () => {
    const dispatch: ChatWorkspaceDispatch = vi.fn();
    const client: ChatWorkflowClient = {
      runChatWorkflow: vi.fn(),
      fetchChatSession: vi.fn(async () => ({
        sessionId: "session-empty",
        memory: [],
        documentIds: [],
        createdAt: "2024-01-01T00:00:00.000Z",
        updatedAt: "2024-01-01T00:00:00.000Z",
        lastInteractionAt: "2024-01-01T00:00:00.000Z",
        preferences: null,
      })),
    };
    localStorage.setItem(CHAT_SESSION_STORAGE_KEY, "session-empty");

    const { unmount } = renderHook(() =>
      useSessionRestoration({ current: client }, dispatch, 0, true)
    );

    await waitFor(() => {
      expect(dispatch).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "RESTORATION_SUCCESS",
          payload: expect.objectContaining({
            sessionId: "session-empty",
            conversation: [],
            lastQuestion: null,
          }),
        })
      );
    });

    unmount();
  });

  it("retries restoration when the workflow client fails", async () => {
    const warnSpy = vi
      .spyOn(console, "warn")
      .mockImplementation(() => undefined);
    const dispatch: ChatWorkspaceDispatch = vi.fn();
    const client: ChatWorkflowClient = {
      runChatWorkflow: vi.fn(),
      fetchChatSession: vi.fn(async () => {
        throw new Error("network down");
      }),
    };
    localStorage.setItem(CHAT_SESSION_STORAGE_KEY, "session-456");

    const { unmount } = renderHook(() =>
      useSessionRestoration({ current: client }, dispatch, 0, true)
    );

    try {
      await waitFor(() => {
        expect(dispatch).toHaveBeenCalledWith(
          expect.objectContaining({
            type: "RESTORATION_ERROR",
            error: "network down",
          })
        );
      });

      await waitFor(
        () => {
          expect(dispatch).toHaveBeenCalledWith({ type: "RESTORATION_RETRY" });
        },
        { timeout: 1500 }
      );
    } finally {
      warnSpy.mockRestore();
      unmount();
    }
  });

  it("clears corrupted sessions and completes when retry is disabled", async () => {
    const warnSpy = vi
      .spyOn(console, "warn")
      .mockImplementation(() => undefined);
    const dispatch: ChatWorkspaceDispatch = vi.fn();
    const invalidState = {
      sessionId: "",
      memory: [
        {
          question: "Q",
          answer: null,
          citations: [],
        },
      ],
      preferences: null,
    } as unknown as ChatSessionState;
    const client: ChatWorkflowClient = {
      runChatWorkflow: vi.fn(),
      fetchChatSession: vi.fn(async () => invalidState),
    };
    localStorage.setItem(CHAT_SESSION_STORAGE_KEY, "session-789");

    const { unmount } = renderHook(() =>
      useSessionRestoration({ current: client }, dispatch, 2, false)
    );

    await waitFor(() => {
      expect(dispatch).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "RESTORATION_ERROR",
          error: "Invalid session data: missing session ID",
        })
      );
    });

    await waitFor(() => {
      expect(dispatch).toHaveBeenCalledWith({ type: "RESTORATION_COMPLETE" });
    });

    expect(localStorage.getItem(CHAT_SESSION_STORAGE_KEY)).toBeNull();
    warnSpy.mockRestore();
    unmount();
  });

  it("completes restoration when the stored session no longer exists", async () => {
    const dispatch: ChatWorkspaceDispatch = vi.fn();
    const client: ChatWorkflowClient = {
      runChatWorkflow: vi.fn(),
      fetchChatSession: vi.fn(async () => null),
    };
    localStorage.setItem(CHAT_SESSION_STORAGE_KEY, "session-stale");

    const { unmount } = renderHook(() =>
      useSessionRestoration({ current: client }, dispatch, 1, false)
    );

    await waitFor(() => {
      expect(dispatch).toHaveBeenCalledWith({ type: "START_RESTORATION" });
    });

    await waitFor(() => {
      expect(dispatch).toHaveBeenCalledWith({ type: "RESTORATION_COMPLETE" });
    });

    expect(localStorage.getItem(CHAT_SESSION_STORAGE_KEY)).toBeNull();
    unmount();
  });

  it("stops retrying after exceeding the backoff schedule", async () => {
    const warnSpy = vi
      .spyOn(console, "warn")
      .mockImplementation(() => undefined);
    const dispatch: ChatWorkspaceDispatch = vi.fn();
    const client: ChatWorkflowClient = {
      runChatWorkflow: vi.fn(),
      fetchChatSession: vi.fn(async () => {
        throw new Error("network down");
      }),
    };
    localStorage.setItem(CHAT_SESSION_STORAGE_KEY, "session-max-attempts");

    const { unmount } = renderHook(() =>
      useSessionRestoration({ current: client }, dispatch, 3, true)
    );

    await waitFor(() => {
      expect(dispatch).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "RESTORATION_ERROR",
          error: "network down",
        })
      );
    });

    await waitFor(() => {
      expect(dispatch).toHaveBeenCalledWith({ type: "RESTORATION_COMPLETE" });
    });

    expect(localStorage.getItem(CHAT_SESSION_STORAGE_KEY)).toBeNull();
    warnSpy.mockRestore();
    unmount();
  });
});

describe("useSessionPersistence", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("writes and clears the persisted session id", async () => {
    const { rerender, unmount } = renderHook<void, { sessionId: string | null }>(
      ({ sessionId }) => useSessionPersistence(sessionId),
      { initialProps: { sessionId: null } },
    );

    rerender({ sessionId: "session-abc" });
    await waitFor(() => {
      expect(localStorage.getItem(CHAT_SESSION_STORAGE_KEY)).toBe("session-abc");
    });

    rerender({ sessionId: null });
    await waitFor(() => {
      expect(localStorage.getItem(CHAT_SESSION_STORAGE_KEY)).toBeNull();
    });

    unmount();
  });
});
