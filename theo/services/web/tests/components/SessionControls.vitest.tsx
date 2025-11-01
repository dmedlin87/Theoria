import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SessionControls } from "../../app/chat/components/SessionControls";

describe("SessionControls", () => {
  it("exposes reset and fork actions through the session menu", async () => {
    const handleReset = vi.fn();
    const handleFork = vi.fn();
    const user = userEvent.setup();

    render(<SessionControls disabled={false} onReset={handleReset} onFork={handleFork} />);

    const trigger = screen.getByRole("button", { name: /session actions/i });
    await user.click(trigger);

    const forkOption = await screen.findByRole("menuitem", { name: /fork conversation/i });
    await user.click(forkOption);
    expect(handleFork).toHaveBeenCalledTimes(1);

    await user.click(trigger);

    const resetOption = await screen.findByRole("menuitem", { name: /reset session/i });
    await user.click(resetOption);

    const confirm = await screen.findByRole("button", { name: /reset session/i });
    await user.click(confirm);
    expect(handleReset).toHaveBeenCalledTimes(1);
  });

  it("is inert when disabled", async () => {
    const handleReset = vi.fn();
    const handleFork = vi.fn();
    const user = userEvent.setup();

    render(<SessionControls disabled onReset={handleReset} onFork={handleFork} />);

    const trigger = screen.getByRole("button", { name: /session actions/i });
    expect(trigger).toBeDisabled();

    await user.click(trigger);
    expect(handleReset).not.toHaveBeenCalled();
    expect(handleFork).not.toHaveBeenCalled();
  });
});
