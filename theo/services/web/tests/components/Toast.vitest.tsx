import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ToastProvider, useToast } from "../../app/components/Toast";

function ToastTester({ duration }: { duration?: number }) {
  const { addToast } = useToast();
  return (
    <button
      type="button"
      onClick={() =>
        addToast({ type: "info", title: "Notification", message: "Toast message", duration: duration ?? 0 })
      }
    >
      Trigger toast
    </button>
  );
}

describe("ToastProvider", () => {
  afterEach(() => {
    vi.useRealTimers();
    cleanup();
  });

  it("renders a toast when addToast is called", async () => {
    render(
      <ToastProvider>
        <ToastTester />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Trigger toast" }));

    const toastDescription = await screen.findByText("Toast message", { selector: "div" });
    expect(toastDescription).toBeInTheDocument();
    expect(screen.getByText("Notification")).toBeInTheDocument();

    const liveRegion = screen
      .getAllByRole("status")
      .find((element) => element.textContent?.includes("Toast message"));

    expect(liveRegion).toBeDefined();
    expect(liveRegion).toHaveAttribute("aria-live", "polite");
  });

  it("allows toasts to be dismissed manually", async () => {
    render(
      <ToastProvider>
        <ToastTester />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Trigger toast" }));
    await screen.findByText("Toast message", { selector: "div" });
    fireEvent.click(screen.getByRole("button", { name: "Dismiss notification" }));
    await waitFor(() => {
      expect(screen.queryByText("Toast message", { selector: "div" })).not.toBeInTheDocument();
    });
  });

  it("auto-dismisses toasts after the provided duration", async () => {
    render(
      <ToastProvider>
        <ToastTester duration={50} />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Trigger toast" }));

    await screen.findByText("Toast message", { selector: "div" });

    await waitFor(() => {
      expect(screen.queryByText("Toast message", { selector: "div" })).not.toBeInTheDocument();
    });
  });
});
