import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { forwardRef, type SVGProps } from "react";

import { Icon } from "../../app/components/Icon";

describe("Icon", () => {
  afterEach(() => {
    cleanup();
  });

  const DummyIcon = forwardRef<SVGSVGElement, SVGProps<SVGSVGElement>>(function DummyIcon(props, ref) {
    return <svg ref={ref} data-testid="dummy-icon" {...props} />;
  });

  it("hides decorative icons from assistive technology by default", () => {
    render(<Icon icon={DummyIcon} data-testid="decorative" />);

    const icon = screen.getByTestId("decorative");
    expect(icon).toHaveAttribute("aria-hidden", "true");
    expect(icon).not.toHaveAttribute("role");
  });

  it("exposes meaningful icons with an accessible name when decorative is false", () => {
    render(<Icon icon={DummyIcon} decorative={false} label="Search" />);

    expect(screen.getByRole("img", { name: "Search" })).toBeInTheDocument();
  });
});
