/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import ChatWorkspace from "../../../app/chat/ChatWorkspace";
import type { ChatWorkflowClient } from "../../../app/lib/chat-client";
import { TheoApiError } from "../../../app/lib/api-client";

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

describe("ChatWorkspace error translations", () => {
  const INPUT_LABEL = "Ask Theoria";

  function renderChat(client: ChatWorkflowClient) {
    return render(<ChatWorkspace client={client} />);
  }

  beforeEach(() => {
    jest.clearAllMocks();
    window.localStorage.clear();
  });

  it("prompts the user to add an API key for authentication failures", async () => {
    const client: ChatWorkflowClient = {
      runChatWorkflow: jest.fn(async () => {
        throw new TheoApiError("Unauthorized", 401, "https://api.test/chat");
      }),
      fetchChatSession: jest.fn(async () => null),
    };

    renderChat(client);

    fireEvent.change(screen.getByLabelText(INPUT_LABEL), { target: { value: "Explain John 1" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(
        screen.getByText(
          /Theo couldn’t authenticate with the API\. Add a valid API key in Settings/i,
        ),
      ).toBeInTheDocument();
    });

    const helpLink = screen.getByRole("link", { name: "Open Settings" });
    expect(helpLink).toHaveAttribute("href", "/admin/settings");
  });

  it("surfaces retry guidance for server failures", async () => {
    const client: ChatWorkflowClient = {
      runChatWorkflow: jest.fn(async () => {
        throw new TheoApiError("Service unavailable", 503, "https://api.test/chat");
      }),
      fetchChatSession: jest.fn(async () => null),
    };

    renderChat(client);

    fireEvent.change(screen.getByLabelText(INPUT_LABEL), { target: { value: "Explain John 1" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(
        screen.getByText(/Theo’s services are having trouble responding\. Please retry in a moment\./i),
      ).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: "Retry question" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Check system status" })).toHaveAttribute(
      "href",
      "https://status.theo.ai/",
    );
  });
});
