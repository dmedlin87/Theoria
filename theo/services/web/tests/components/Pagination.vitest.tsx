import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import Pagination from "../../app/components/Pagination";

describe("Pagination", () => {
  it("renders nothing when there is only one page", () => {
    const { container } = render(
      <Pagination currentPage={1} totalPages={1} onPageChange={() => {}} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders ellipses when the current page has distant neighbours", () => {
    render(<Pagination currentPage={5} totalPages={9} onPageChange={() => {}} />);
    expect(screen.getAllByText("…")).toHaveLength(2);
  });

  it("invokes the callback when a page is selected", async () => {
    const onPageChange = vi.fn();
    const user = userEvent.setup();

    const view = render(
      <Pagination currentPage={2} totalPages={3} onPageChange={onPageChange} />,
    );

    await user.click(view.getByRole("button", { name: "Page 3" }));
    expect(onPageChange).toHaveBeenCalledWith(3);

    await user.click(view.getByRole("button", { name: "Previous page" }));
    expect(onPageChange).toHaveBeenCalledWith(1);
  });
});
