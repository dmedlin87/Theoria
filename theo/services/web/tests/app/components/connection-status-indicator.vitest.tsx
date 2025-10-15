import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import ConnectionStatusIndicator from "../../../app/components/ConnectionStatusIndicator";
import type { ApiHealthSnapshot, ApiHealthStatus } from "../../../app/lib/useApiHealth";

const { mockUseApiHealth } = vi.hoisted(() => ({
  mockUseApiHealth: vi.fn<[], ApiHealthSnapshot>(),
}));

vi.mock("../../../app/lib/useApiHealth", () => ({
  useApiHealth: mockUseApiHealth,
}));

vi.mock("../../../app/components/Toast", () => ({
  useToast: () => ({ addToast: vi.fn(), removeToast: vi.fn(), toasts: [] }),
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
  });
});
