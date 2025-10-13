/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SessionControls } from "../../app/chat/components/SessionControls";

describe("SessionControls", () => {
  it("supports keyboard interaction for menu items", async () => {
    const onReset = jest.fn();
    const onFork = jest.fn();
    const user = userEvent.setup();

    render(<SessionControls disabled={false} onReset={onReset} onFork={onFork} />);

    const trigger = screen.getByRole("button", { name: /session actions/i });
    expect(trigger).toBeEnabled();

    await user.tab();
    expect(trigger).toHaveFocus();

    await user.keyboard("{Enter}");

    const forkItem = await screen.findByRole("menuitem", { name: /fork conversation/i });
    expect(forkItem).toBeVisible();

    await user.keyboard("{Enter}");
    expect(onFork).toHaveBeenCalledTimes(1);
  });

  it("opens a confirmation dialog before resetting", async () => {
    const onReset = jest.fn();
    const user = userEvent.setup();

    render(<SessionControls disabled={false} onReset={onReset} onFork={() => undefined} />);

    await user.click(screen.getByRole("button", { name: /session actions/i }));
    const resetItem = await screen.findByRole("menuitem", { name: /reset session/i });
    await user.click(resetItem);

    const dialog = await screen.findByRole("dialog", { name: /reset this session/i });
    expect(dialog).toBeVisible();

    const confirmButton = within(dialog).getByRole("button", { name: /reset session/i });
    await user.click(confirmButton);

    expect(onReset).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog", { name: /reset this session/i })).not.toBeInTheDocument();
  });
});
