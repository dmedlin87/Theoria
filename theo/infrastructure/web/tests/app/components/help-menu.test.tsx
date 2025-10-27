import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { HelpMenu } from "../../../app/components/help/HelpMenu";

describe("HelpMenu", () => {
  it("renders documentation links with expected targets", async () => {
    render(<HelpMenu />);

    const trigger = screen.getByRole("button", { name: /help/i });
    await userEvent.click(trigger);

    const gettingStarted = await screen.findByRole("menuitem", {
      name: /getting started guide/i,
    });
    expect(gettingStarted).toHaveAttribute("href");
    expect(gettingStarted.getAttribute("href")).toContain("START_HERE.md");

    const readme = screen.getByRole("menuitem", { name: /project readme/i });
    expect(readme).toHaveAttribute("href");
    expect(readme.getAttribute("href")).toContain("README.md");

    const apiDocs = screen.getByRole("menuitem", { name: /api reference/i });
    expect(apiDocs).toHaveAttribute("href");
    expect(apiDocs.getAttribute("href")).toContain("docs");

    const auth = screen.getByRole("menuitem", { name: /authentication troubleshooting/i });
    expect(auth).toHaveAttribute("href");
    expect(auth.getAttribute("href")).toContain("api-authentication");
  });

  it("supports keyboard interaction", async () => {
    render(<HelpMenu />);

    await userEvent.tab();
    const trigger = screen.getByRole("button", { name: /help/i });
    expect(trigger).toHaveFocus();

    await userEvent.keyboard("{Enter}");
    const keyboardItem = await screen.findByRole("menuitem", { name: /keyboard shortcuts/i });
    expect(keyboardItem).toBeVisible();

    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("menuitem", { name: /keyboard shortcuts/i })).not.toBeInTheDocument();
  });
});
