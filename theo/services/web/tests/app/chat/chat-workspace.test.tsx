/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import type {
  ChatWorkflowClient,
  ChatWorkflowResult,
  ChatWorkflowStreamEvent,
} from "../../../app/lib/chat-client";
import ChatWorkspace from "../../../app/chat/ChatWorkspace";
import { TheoApiError } from "../../../app/lib/api-client";
import { emitTelemetry, submitFeedback } from "../../../app/lib/telemetry";

jest.mock("../../../app/lib/telemetry", () => ({
  submitFeedback: jest.fn(),
  emitTelemetry: jest.fn(),
}));

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
  }),
}));

const sampleAnswer = {
  summary: "The prologue echoes Genesis, presenting the Logos as divine and eternal.",
  citations: [
    {
      index: 0,
      osis: "John.1.1",
      anchor: "John 1:1",
      passage_id: "passage-1",
      document_id: "doc-1",
      document_title: "Sample Commentary",
      snippet: "In the beginning was the Word, and the Word was with God.",
      source_url: null,
    },
  ],
  model_name: null,
  model_output: null,
  guardrail_profile: null,
} satisfies import("../../../app/copilot/components/types").RAGAnswer;

jest.mock("../../../app/mode-context", () => {
  const { RESEARCH_MODES, DEFAULT_MODE_ID } =
    jest.requireActual<typeof import("../../../app/mode-config")>(
      "../../../app/mode-config",
    );
  return {
    useMode: () => ({
      mode: RESEARCH_MODES[DEFAULT_MODE_ID],
      modes: Object.values(RESEARCH_MODES),
      setMode: jest.fn(),
    }),
  };
});

const STORAGE_KEY = "theo.chat.lastSessionId";
const INPUT_LABEL = "Ask Theoria";

describe("ChatWorkspace", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    window.localStorage.clear();
  });

  it("prefills the textarea when a sample question chip is clicked", () => {
    const client: ChatWorkflowClient = {
      runChatWorkflow: jest.fn(),
      fetchChatSession: jest.fn(async () => null),
    };
    const telemetryMock = emitTelemetry as jest.MockedFunction<typeof emitTelemetry>;
    telemetryMock.mockResolvedValue(undefined);

    render(<ChatWorkspace client={client} />);

    const textarea = screen.getByLabelText(INPUT_LABEL) as HTMLTextAreaElement;
    expect(textarea).toHaveValue("");

    const sampleChip = screen.getByRole("button", {
      name: "How does John 1:1 connect with Genesis 1?",
    });

    fireEvent.click(sampleChip);

    expect(textarea).toHaveValue("How does John 1:1 connect with Genesis 1?");
    expect(telemetryMock).toHaveBeenCalledWith(
      [
        expect.objectContaining({
          event: "chat.sample_question_click",
          metadata: expect.objectContaining({ index: 0 }),
        }),
      ],
      { page: "chat" },
    );
  });

  it("streams a chat response, updates incrementally, and persists the session id", async () => {
    const successResult: ChatWorkflowResult = {
      kind: "success",
      sessionId: "session-1",
      answer: sampleAnswer,
    };
    const client: ChatWorkflowClient = {
      runChatWorkflow: jest.fn(async (_payload, options) => {
        options?.onEvent?.({ type: "answer_fragment", content: "In the beginning" });
        await new Promise((resolve) => setTimeout(resolve, 5));
        options?.onEvent?.({
          type: "complete",
          response: { sessionId: "session-1", answer: sampleAnswer },
        });
        return successResult;
      }),
      fetchChatSession: jest.fn(async () => null),
    };

    render(<ChatWorkspace client={client} />);

    fireEvent.change(screen.getByLabelText(INPUT_LABEL), {
      target: { value: "Explain John 1:1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("In the beginning")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(sampleAnswer.summary)).toBeInTheDocument();
    });

    expect(
      screen.getByRole("link", { name: "Open John 1:1" })
    ).toHaveAttribute("href", "/verse/John.1.1");
    expect(screen.getByRole("link", { name: "Search references" })).toHaveAttribute(
      "href",
      "/search?osis=John.1.1",
    );
    await waitFor(() => {
      expect(window.localStorage.getItem(STORAGE_KEY)).toBe("session-1");
    });
    expect(client.runChatWorkflow).toHaveBeenCalledWith(
      expect.objectContaining({ modeId: "balanced" }),
      expect.objectContaining({ onEvent: expect.any(Function) }),
    );
  });

  it("surface guardrail violations with actionable messaging", async () => {
    const guardrailResult: ChatWorkflowResult = {
      kind: "guardrail",
      message: "Blocked by safeguards",
      traceId: "trace-123",
      suggestions: [
        {
          action: "search",
          label: "Search related passages",
          description: "Open the search workspace to inspect passages.",
          query: "Share restricted content",
          osis: null,
          filters: null,
        },
      ],
      metadata: null,
    };
    const client: ChatWorkflowClient = {
      runChatWorkflow: jest.fn(async (_payload, options) => {
        const guardrailEvent: ChatWorkflowStreamEvent = {
          type: "guardrail_violation",
          message: "Blocked by safeguards",
          traceId: "trace-123",
          suggestions: guardrailResult.suggestions,
          metadata: null,
        };
        options?.onEvent?.(guardrailEvent);
        return guardrailResult;
      }),
      fetchChatSession: jest.fn(async () => null),
    };

    render(<ChatWorkspace client={client} />);

    fireEvent.change(screen.getByLabelText(INPUT_LABEL), {
      target: { value: "Share restricted content" },
    });
    const sendButton = screen.getByRole("button", { name: "Send" });
    await waitFor(() => expect(sendButton).not.toBeDisabled());
    fireEvent.click(sendButton);

    expect(await screen.findByText("Blocked by safeguards")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Rephrase question" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Search related passages" })
    ).toBeInTheDocument();
  });

  it("shows a fallback error callout when the workflow fails", async () => {
    const client: ChatWorkflowClient = {
      runChatWorkflow: jest.fn(async () => {
        throw new Error("Network offline");
      }),
      fetchChatSession: jest.fn(async () => null),
    };

    render(<ChatWorkspace client={client} />);

    fireEvent.change(screen.getByLabelText(INPUT_LABEL), {
      target: { value: "Explain John 1:1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Network offline");
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(screen.queryByText(sampleAnswer.summary)).not.toBeInTheDocument();
  });

  it("offers fallback suggestions when the API rejects the prompt", async () => {
    const client: ChatWorkflowClient = {
      runChatWorkflow: jest.fn(async () => {
        throw new TheoApiError("Prompt invalid", 400);
      }),
      fetchChatSession: jest.fn(async () => null),
    };

    render(<ChatWorkspace client={client} />);

    fireEvent.change(screen.getByLabelText(INPUT_LABEL), {
      target: { value: "Explain John 1:1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Prompt invalid");
    expect(
      screen.getByRole("button", { name: "Upload supporting documents" })
    ).toBeInTheDocument();
  });

  it("sends feedback when reaction buttons are pressed", async () => {
    const events: ChatWorkflowStreamEvent[] = [
      { type: "answer_fragment", content: "In the beginning" },
      { type: "complete", response: { sessionId: "session-1", answer: sampleAnswer } },
    ];
    const successResult: ChatWorkflowResult = {
      kind: "success",
      sessionId: "session-1",
      answer: sampleAnswer,
    };
    const client: ChatWorkflowClient = {
      runChatWorkflow: jest.fn(async (_payload, options) => {
        events.forEach((event) => options?.onEvent?.(event));
        return successResult;
      }),
      fetchChatSession: jest.fn(async () => null),
    };

    const submitMock = submitFeedback as jest.MockedFunction<typeof submitFeedback>;
    submitMock.mockResolvedValue(undefined);

    render(<ChatWorkspace client={client} />);

    fireEvent.change(screen.getByLabelText(INPUT_LABEL), {
      target: { value: "Explain John 1:1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(screen.getByText(sampleAnswer.summary)).toBeInTheDocument();
    });

    const helpfulButton = screen.getByRole("button", { name: "Mark response helpful" });
    const unhelpfulButton = screen.getByRole("button", { name: "Mark response unhelpful" });

    let resolveFeedback: (() => void) | undefined;
    const pendingFeedback = new Promise<void>((resolve) => {
      resolveFeedback = resolve;
    });
    submitMock.mockReturnValueOnce(pendingFeedback);

    fireEvent.click(helpfulButton);

    expect(helpfulButton).toBeDisabled();
    expect(unhelpfulButton).toBeDisabled();
    expect(submitMock).toHaveBeenCalledWith(
      expect.objectContaining({
        action: "like",
        chatSessionId: "session-1",
        query: "Explain John 1:1",
      }),
    );

    resolveFeedback?.();
    await waitFor(() => expect(helpfulButton).not.toBeDisabled());
    expect(helpfulButton).toHaveAttribute("aria-pressed", "true");
    expect(unhelpfulButton).toHaveAttribute("aria-pressed", "false");
  });

  it("resets feedback controls when submission fails", async () => {
    const successResult: ChatWorkflowResult = {
      kind: "success",
      sessionId: "session-99",
      answer: sampleAnswer,
    };
    const client: ChatWorkflowClient = {
      runChatWorkflow: jest.fn(async (_payload, options) => {
        options?.onEvent?.({ type: "complete", response: { sessionId: "session-99", answer: sampleAnswer } });
        return successResult;
      }),
      fetchChatSession: jest.fn(async () => null),
    };

    const submitMock = submitFeedback as jest.MockedFunction<typeof submitFeedback>;
    submitMock.mockRejectedValueOnce(new Error("failed"));

    render(<ChatWorkspace client={client} />);

    fireEvent.change(screen.getByLabelText(INPUT_LABEL), {
      target: { value: "Explain John 1:1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(screen.getByText(sampleAnswer.summary)).toBeInTheDocument();
    });

    const helpfulButton = screen.getByRole("button", { name: "Mark response helpful" });
    const unhelpfulButton = screen.getByRole("button", { name: "Mark response unhelpful" });

    fireEvent.click(unhelpfulButton);

    expect(helpfulButton).toBeDisabled();
    expect(unhelpfulButton).toBeDisabled();

    await waitFor(() => {
      expect(helpfulButton).not.toBeDisabled();
      expect(unhelpfulButton).not.toBeDisabled();
    });

    expect(helpfulButton).toHaveAttribute("aria-pressed", "false");
    expect(unhelpfulButton).toHaveAttribute("aria-pressed", "false");
  });

  it("resets the session state and clears persistence", async () => {
    const successResult: ChatWorkflowResult = {
      kind: "success",
      sessionId: "session-reset",
      answer: sampleAnswer,
    };
    const client: ChatWorkflowClient = {
      runChatWorkflow: jest.fn(async (_payload, options) => {
        options?.onEvent?.({
          type: "complete",
          response: { sessionId: "session-reset", answer: sampleAnswer },
        });
        return successResult;
      }),
      fetchChatSession: jest.fn(async () => null),
    };

    render(<ChatWorkspace client={client} />);

    fireEvent.change(screen.getByLabelText(INPUT_LABEL), {
      target: { value: "Explain John 1:1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(screen.getByText(sampleAnswer.summary)).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(window.localStorage.getItem(STORAGE_KEY)).toBe("session-reset");
    });

    const resetButton = screen.getByRole("button", { name: "Reset session" });
    await waitFor(() => expect(resetButton).not.toBeDisabled());

    fireEvent.click(resetButton);

    await waitFor(() => {
      expect(screen.queryByText(sampleAnswer.summary)).not.toBeInTheDocument();
    });
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it("forks the conversation without losing the transcript", async () => {
    const successResult: ChatWorkflowResult = {
      kind: "success",
      sessionId: "session-fork",
      answer: sampleAnswer,
    };
    const client: ChatWorkflowClient = {
      runChatWorkflow: jest.fn(async (_payload, options) => {
        options?.onEvent?.({
          type: "complete",
          response: { sessionId: "session-fork", answer: sampleAnswer },
        });
        return successResult;
      }),
      fetchChatSession: jest.fn(async () => null),
    };

    render(<ChatWorkspace client={client} />);

    fireEvent.change(screen.getByLabelText(INPUT_LABEL), {
      target: { value: "Explain John 1:1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(screen.getByText(sampleAnswer.summary)).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(window.localStorage.getItem(STORAGE_KEY)).toBe("session-fork");
    });

    const forkButton = screen.getByRole("button", { name: "Fork conversation" });
    await waitFor(() => expect(forkButton).not.toBeDisabled());

    fireEvent.click(forkButton);

    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(screen.getByText(sampleAnswer.summary)).toBeInTheDocument();
  });

  it("auto-submits new prompts when initialPrompt changes", async () => {
    const client: ChatWorkflowClient = {
      runChatWorkflow: jest.fn(async () => ({
        kind: "success" as const,
        sessionId: "session-1",
        answer: sampleAnswer,
      })),
      fetchChatSession: jest.fn(async () => null),
    };

    const { rerender } = render(
      <ChatWorkspace client={client} initialPrompt="Explain John 1" autoSubmit />,
    );

    await waitFor(() => {
      expect(client.runChatWorkflow).toHaveBeenNthCalledWith(
        1,
        expect.objectContaining({ prompt: "Explain John 1" }),
        expect.objectContaining({ onEvent: expect.any(Function) }),
      );
    });

    rerender(
      <ChatWorkspace client={client} initialPrompt="Summarize Romans 8" autoSubmit />,
    );

    await waitFor(() => {
      expect(client.runChatWorkflow).toHaveBeenNthCalledWith(
        2,
        expect.objectContaining({ prompt: "Summarize Romans 8" }),
        expect.objectContaining({ onEvent: expect.any(Function) }),
      );
    });

    expect(client.runChatWorkflow).toHaveBeenCalledTimes(2);
  });
});
