import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ToastProvider, useToast } from "../../app/components/Toast";

describe("ToastProvider", () => {
  it("renders toasts inside an aria-live region", async () => {
    const user = userEvent.setup({ delay: null });

    function Example() {
      const { addToast } = useToast();
      return (
        <button
          type="button"
          onClick={() => addToast({ type: "success", message: "Saved" })}
        >
          Trigger toast
        </button>
      );
    }

    render(
      <ToastProvider>
        <Example />
      </ToastProvider>,
    );

    await user.click(screen.getByRole("button", { name: /trigger toast/i }));

    const region = screen.getByRole("region", { name: "Notifications" });
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(region).toHaveAttribute("aria-atomic", "true");
    expect(
      screen.getByRole("alert", { name: undefined, hidden: false }),
    ).toHaveTextContent("Saved");
  });

  it("dismisses toasts when the close button is activated", async () => {
    const user = userEvent.setup({ delay: null });

    function Example() {
      const { addToast } = useToast();
      return (
        <button
          type="button"
          onClick={() => addToast({ type: "info", message: "Queued", duration: 0 })}
        >
          Notify
        </button>
      );
    }

    render(
      <ToastProvider>
        <Example />
      </ToastProvider>,
    );

    await user.click(screen.getByRole("button", { name: /notify/i }));

    const dismiss = screen.getByRole("button", { name: /dismiss notification/i });
    await user.click(dismiss);

    expect(screen.queryByRole("alert")).toBeNull();
  });
});
