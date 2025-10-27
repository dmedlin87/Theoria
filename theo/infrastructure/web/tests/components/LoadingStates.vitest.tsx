import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { LoadingOverlay, Skeleton, SkeletonText, Spinner } from "../../app/components/LoadingStates";

describe("LoadingStates", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders a skeleton with custom dimensions", () => {
    const { container } = render(<Skeleton width="120px" height="24px" />);

    const skeleton = container.firstElementChild as HTMLElement;
    expect(skeleton).toHaveClass("skeleton");
    expect(skeleton).toHaveStyle({ width: "120px", height: "24px" });
  });

  it("renders the requested number of skeleton text lines", () => {
    const { container } = render(<SkeletonText lines={4} />);

    const skeletonLines = container.querySelectorAll(".skeleton-text");
    expect(skeletonLines).toHaveLength(4);
  });

  it("provides accessible spinner semantics", () => {
    render(<Spinner size="lg" />);

    const spinner = screen.getByRole("status", { name: "Loading" });
    expect(spinner).toHaveClass("spinner");
  });

  it("renders a loading overlay with message", () => {
    render(<LoadingOverlay message="Syncing" />);

    expect(screen.getByRole("alert")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByText("Syncing")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
  });
});
