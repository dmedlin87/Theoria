import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ToastProvider, ToastType, useToast } from "../../app/components/Toast";
import { toastVariants } from "../../app/components/ui/toast";

function ToastTester({
  duration,
  toastType = "info",
  message = "Toast message",
  title = "Notification",
}: {
  duration?: number;
  toastType?: ToastType;
  message?: string;
  title?: string;
}) {
  const { addToast } = useToast();
  return (
    <button
      type="button"
      onClick={() =>
        addToast({ type: toastType, title, message, duration: duration ?? 0 })
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

  it("renders a toast when addToast is called with accessible labelling", async () => {
    render(
      <ToastProvider>
        <ToastTester />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Trigger toast" }));

    const regionCandidates = await screen.findAllByRole("region", { name: /Notifications/i });
    const toastRegion = regionCandidates.find(
      (region) => region.getAttribute("aria-live") === "polite" && region.getAttribute("aria-atomic") === "false",
    );

    expect(toastRegion).toBeDefined();
    expect(toastRegion).toHaveAttribute("aria-live", "polite");
    expect(toastRegion).toHaveAttribute("aria-atomic", "false");

    const toastDescription = await screen.findByText("Toast message", { selector: "div" });
    expect(toastDescription).toBeInTheDocument();
    expect(screen.getByText("Notification")).toBeInTheDocument();

    const liveRegions = await screen.findAllByRole("status", { hidden: true });
    const toastStatus = liveRegions.find((element) => element.textContent?.includes("Toast message"));

    expect(toastStatus).toBeDefined();
    expect(toastStatus).toHaveAttribute("aria-live", "polite");
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

  it("applies success variant styling", async () => {
    render(
      <ToastProvider>
        <ToastTester toastType="success" message="Success!" title="Success" />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Trigger toast" }));

    const toastDescription = await screen.findByText("Success!", { selector: "div" });
    const toastRoot = toastDescription.closest("[data-state]");

    expect(toastRoot).not.toBeNull();
    expect(toastRoot?.className).toContain(toastVariants.success);
    expect(toastRoot).toHaveClass("slide-up", "bounce");
  });

  it("applies error variant styling", async () => {
    render(
      <ToastProvider>
        <ToastTester toastType="error" message="Failure" title="Error" />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Trigger toast" }));

    const toastDescription = await screen.findByText("Failure", { selector: "div" });
    const toastRoot = toastDescription.closest("[data-state]");

    expect(toastRoot).not.toBeNull();
    expect(toastRoot?.className).toContain(toastVariants.error);
    expect(toastRoot).toHaveClass("slide-up", "shake");
  });
});
