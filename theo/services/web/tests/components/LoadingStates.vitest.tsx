import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  LoadingOverlay,
  Skeleton,
  SkeletonList,
  SkeletonText,
  Spinner,
} from "../../app/components/LoadingStates";

describe("LoadingStates components", () => {
  it("applies dimensions to skeleton blocks", () => {
    const { container } = render(<Skeleton width="10rem" height={24} />);
    const skeleton = container.firstElementChild as HTMLElement;
    expect(skeleton).toHaveClass("skeleton");
    expect(skeleton).toHaveStyle({ width: "10rem" });
    expect(skeleton).toHaveStyle({ height: "24px" });
  });

  it("renders the requested number of skeleton text rows", () => {
    const { container } = render(<SkeletonText lines={4} />);
    const rows = container.querySelectorAll(".skeleton-text");
    expect(rows).toHaveLength(4);
  });

  it("marks the spinner as a polite status", () => {
    render(<Spinner size="lg" />);
    const spinner = screen.getByRole("status", { name: "Loading" });
    expect(spinner).toBeInTheDocument();
    expect(spinner.querySelector(".sr-only")).toHaveTextContent("Loading...");
  });

  it("exposes the loading overlay with the expected ARIA attributes", () => {
    render(<LoadingOverlay message="Indexing" />);
    const overlay = screen.getByRole("alert", { name: "" });
    expect(overlay).toHaveAttribute("aria-busy", "true");
    expect(overlay).toHaveAttribute("aria-live", "polite");
    expect(screen.getByText("Indexing")).toBeVisible();
  });

  it("renders the requested number of skeleton cards in a list", () => {
    const { container } = render(<SkeletonList count={2} />);
    const cards = container.querySelectorAll(".card");
    expect(cards).toHaveLength(2);
  });
});
