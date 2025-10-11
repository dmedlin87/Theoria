/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import type {
  ChatWorkflowClient,
  ChatWorkflowResult,
  ChatWorkflowStreamEvent,
} from "../../../app/lib/chat-client";
import ChatWorkspace from "../../../app/chat/ChatWorkspace";
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
  const { RESEARCH_MODES, DEFAULT_MODE_ID } = require("../../../app/mode-config");
  return {
    useMode: () => ({
      mode: RESEARCH_MODES[DEFAULT_MODE_ID],
      modes: Object.values(RESEARCH_MODES),
      setMode: jest.fn(),
    }),
  };
});

describe("ChatWorkspace", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("prefills the textarea when a sample question chip is clicked", () => {
    const client: ChatWorkflowClient = {
      runChatWorkflow: jest.fn(),
      fetchChatSession: jest.fn(async () => null),
    };
    const telemetryMock = emitTelemetry as jest.MockedFunction<typeof emitTelemetry>;
    telemetryMock.mockResolvedValue(undefined);

    render(<ChatWorkspace client={client} />);

    const textarea = screen.getByLabelText("Ask Theo Engine") as HTMLTextAreaElement;
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

  it("streams a chat response and renders citations", async () => {
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

    render(<ChatWorkspace client={client} />);

    fireEvent.change(screen.getByLabelText("Ask Theo Engine"), {
      target: { value: "Explain John 1:1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

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
    expect(client.runChatWorkflow).toHaveBeenCalledWith(
      expect.objectContaining({ modeId: "balanced" }),
      expect.objectContaining({ onEvent: expect.any(Function) }),
    );
  });

  it("surface guardrail violations", async () => {
    const guardrailResult: ChatWorkflowResult = {
      kind: "guardrail",
      message: "Blocked by safeguards",
      traceId: "trace-123",
      suggestions: [],
      metadata: null,
    };
    const client: ChatWorkflowClient = {
      runChatWorkflow: jest.fn(async (_payload, options) => {
        const guardrailEvent: ChatWorkflowStreamEvent = {
          type: "guardrail_violation",
          message: "Blocked by safeguards",
          traceId: "trace-123",
          suggestions: [],
          metadata: null,
        };
        options?.onEvent?.(guardrailEvent);
        return guardrailResult;
      }),
      fetchChatSession: jest.fn(async () => null),
    };

    render(<ChatWorkspace client={client} />);

    fireEvent.change(screen.getByLabelText("Ask Theo Engine"), {
      target: { value: "Share restricted content" },
    });
    const sendButton = screen.getByRole("button", { name: "Send" });
    await waitFor(() => expect(sendButton).not.toBeDisabled());
    fireEvent.click(sendButton);

    expect(await screen.findByText("Blocked by safeguards")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Rephrase question" })).toBeInTheDocument();
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

    fireEvent.change(screen.getByLabelText("Ask Theo Engine"), {
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

  it("auto-submits new prompts when initialPrompt changes", async () => {
    const client: ChatWorkflowClient = {
      runChatWorkflow: jest.fn(async () => ({
        kind: "success",
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
