/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import WorkflowSelector from "../../app/copilot/components/WorkflowSelector";

describe("WorkflowSelector", () => {
  it("announces the selected workflow via aria-pressed", async () => {
    const onSelect = jest.fn();
    const user = userEvent.setup();

    render(
      <WorkflowSelector
        selected="verse"
        options={[
          { id: "verse", label: "Verse study", description: "Focused research for a single passage." },
          { id: "sermon", label: "Sermon prep", description: "Outline messages with citations." },
        ]}
        onSelect={onSelect}
      />,
    );

    const [verseButton, sermonButton] = screen.getAllByRole("button");
    expect(verseButton).toHaveAttribute("aria-pressed", "true");
    expect(sermonButton).toHaveAttribute("aria-pressed", "false");

    await user.tab();
    await user.tab();
    expect(sermonButton).toHaveFocus();

    await user.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledWith("sermon");
  });
});
