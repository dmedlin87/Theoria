/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";

import FallacyWarnings from "../../../app/components/FallacyWarnings";
import type { FallacyWarningModel } from "../../../app/copilot/components/types";

describe("FallacyWarnings", () => {
  const sampleWarnings: FallacyWarningModel[] = [
    {
      fallacy_type: "ad_hominem",
      severity: "high",
      description: "Attacks the opponent instead of the substance of the claim.",
      matched_text: "Only a fool would read the passage that way.",
      suggestion: "Address the actual claim with evidence.",
    },
    {
      fallacy_type: "appeal_to_authority",
      severity: "low",
      description: "Relies solely on experts rather than the cited text.",
      matched_text: "Scholars agree, so it must be true.",
      suggestion: null,
    },
  ];

  it("renders each fallacy with severity indicators", () => {
    const { container } = render(<FallacyWarnings warnings={sampleWarnings} />);

    expect(screen.getByText("Ad Hominem")).toBeInTheDocument();
    expect(screen.getByText("Attacks the opponent instead of the substance of the claim.")).toBeInTheDocument();
    expect(screen.getAllByText("High severity").length).toBeGreaterThan(0);
    expect(screen.getByText("Appeal To Authority")).toBeInTheDocument();

    const wrapper = container.querySelector(".chat-fallacy-warnings");
    expect(wrapper).toHaveClass("chat-fallacy-warnings--high");
  });

  it("renders nothing when warnings are empty", () => {
    const { container, rerender } = render(<FallacyWarnings warnings={[]} />);
    expect(container.firstChild).toBeNull();

    rerender(<FallacyWarnings warnings={null} />);
    expect(container.firstChild).toBeNull();
  });
});
