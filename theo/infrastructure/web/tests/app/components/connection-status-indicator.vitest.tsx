import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import ConnectionStatusIndicator from "../../../app/components/ConnectionStatusIndicator";
import type { ApiHealthSnapshot, ApiHealthStatus } from "../../../app/lib/useApiHealth";

const { mockUseApiHealth, addToastMock } = vi.hoisted(() => ({
  mockUseApiHealth: vi.fn<[], ApiHealthSnapshot>(),
  addToastMock: vi.fn(),
}));

vi.mock("../../../app/lib/useApiHealth", () => ({
  useApiHealth: mockUseApiHealth,
}));

vi.mock("../../../app/components/Toast", () => ({
  useToast: () => ({ addToast: addToastMock, removeToast: vi.fn(), toasts: [] }),
}));

function createSnapshot(overrides: Partial<ApiHealthSnapshot>): ApiHealthSnapshot {
  return {
    status: "healthy",
    message: "API connection is healthy.",
    isChecking: false,
    lastChecked: Date.now(),
    lastError: null,
    refresh: vi.fn(),
    ...overrides,
  };
}

beforeAll(() => {
  class ResizeObserverMock {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  (globalThis as unknown as { ResizeObserver?: unknown }).ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver;
});

describe("ConnectionStatusIndicator", () => {
  afterEach(() => {
    cleanup();
    mockUseApiHealth.mockReset();
    addToastMock.mockReset();
  });

  it.each([
    ["healthy", "Connected", "API connection is healthy."],
    ["degraded", "Degraded", "Latency elevated"],
    ["unauthenticated", "Sign-in required", "Sign in to continue"],
    ["offline", "Offline", "API is not reachable"],
  ] as Array<[ApiHealthStatus, string, string]>)
  ("renders %s badge and tooltip", async (status, label, message) => {
    const user = userEvent.setup();
    mockUseApiHealth.mockReturnValue(
      createSnapshot({ status, message, lastChecked: 1_708_000_000_000 }),
    );

    render(<ConnectionStatusIndicator announce={false} />);

    const trigger = screen.getByRole("button", { name: new RegExp(label, "i") });
    expect(trigger).toHaveAttribute("data-status", status);
    expect(screen.getByText(label)).toBeInTheDocument();

    await user.hover(trigger);
    const tooltip = await screen.findByRole("tooltip");
    expect(tooltip).toHaveTextContent(message);
  });

  it("shows loading state while checking", () => {
    mockUseApiHealth.mockReturnValue(createSnapshot({ status: "offline", isChecking: true }));

    render(<ConnectionStatusIndicator announce={false} />);

    expect(screen.getByText("Checking…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Connection status/i })).toBeDisabled();
  });

  it("renders the inline status message when requested", () => {
    mockUseApiHealth.mockReturnValue(
      createSnapshot({ status: "degraded", message: "Latency elevated" }),
    );

    render(<ConnectionStatusIndicator announce={false} showMessage />);

    expect(screen.getByText("Latency elevated")).toBeInTheDocument();
  });

  it("invokes the refresh handler when the badge is pressed", async () => {
    const refresh = vi.fn();
    mockUseApiHealth.mockReturnValue(
      createSnapshot({ status: "healthy", refresh }),
    );

    const user = userEvent.setup();
    render(<ConnectionStatusIndicator announce={false} />);

    await user.click(screen.getByRole("button", { name: /Connection status/i }));

    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("announces non-healthy transitions and message changes", async () => {
    mockUseApiHealth.mockReturnValueOnce(
      createSnapshot({ status: "healthy", message: "All systems nominal" }),
    );

    const { rerender } = render(<ConnectionStatusIndicator />);

    await waitFor(() => {
      expect(addToastMock).not.toHaveBeenCalled();
    });

    mockUseApiHealth.mockReturnValueOnce(
      createSnapshot({ status: "degraded", message: "Latency elevated" }),
    );

    rerender(<ConnectionStatusIndicator />);

    await waitFor(() => {
      expect(addToastMock).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "warning",
          title: "API health degraded",
          message: "Latency elevated",
        }),
      );
    });

    addToastMock.mockClear();

    mockUseApiHealth.mockReturnValueOnce(
      createSnapshot({ status: "degraded", message: "Error rate increasing" }),
    );

    rerender(<ConnectionStatusIndicator />);

    await waitFor(() => {
      expect(addToastMock).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "warning",
          title: "API health degraded",
          message: "Error rate increasing",
        }),
      );
    });
  });
});
