import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import Pagination from "../../app/components/Pagination";

describe("Pagination", () => {
  afterEach(() => {
    cleanup();
  });

  it("does not render when only one page is available", () => {
    const { container } = render(<Pagination currentPage={1} totalPages={1} onPageChange={() => undefined} />);

    expect(container.firstChild).toBeNull();
  });

  it("renders navigation buttons with correct accessibility labels", () => {
    const onPageChange = vi.fn();
    render(<Pagination currentPage={2} totalPages={5} onPageChange={onPageChange} />);

    expect(screen.getByRole("navigation", { name: "Pagination" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous page" })).not.toBeDisabled();
    expect(screen.getByRole("button", { name: "Next page" })).not.toBeDisabled();
    expect(screen.getByRole("button", { name: "Page 2" })).toBeDisabled();
  });

  it("invokes onPageChange when navigating", async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    render(<Pagination currentPage={1} totalPages={3} onPageChange={onPageChange} />);

    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(onPageChange).toHaveBeenCalledWith(2);

    await user.click(screen.getByRole("button", { name: "Page 3" }));
    expect(onPageChange).toHaveBeenCalledWith(3);
  });

  it("disables previous and next controls at boundaries", () => {
    const onPageChange = vi.fn();
    const { rerender } = render(<Pagination currentPage={1} totalPages={2} onPageChange={onPageChange} />);

    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();

    rerender(<Pagination currentPage={2} totalPages={2} onPageChange={onPageChange} />);
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
  });
});
