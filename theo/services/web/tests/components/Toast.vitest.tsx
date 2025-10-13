import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
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

    expect(await screen.findByRole("alert")).toHaveTextContent("Toast message");
    expect(screen.getByText("Notification")).toBeInTheDocument();
  });

  it("allows toasts to be dismissed manually", async () => {
    render(
      <ToastProvider>
        <ToastTester />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Trigger toast" }));
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "Dismiss notification" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("auto-dismisses toasts after the provided duration", async () => {
    vi.useFakeTimers();

    render(
      <ToastProvider>
        <ToastTester duration={1000} />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Trigger toast" }));

    expect(screen.getByRole("alert")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1100);
    });

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
