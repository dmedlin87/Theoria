/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { render, screen, within } from "@testing-library/react";

import { ReasoningTrace as ReasoningTraceComponent } from "../../../app/components/ReasoningTrace";
import type { ReasoningTrace as ReasoningTraceModel } from "../../../app/lib/reasoning-trace";

describe("ReasoningTrace", () => {
  const sampleTrace: ReasoningTraceModel = {
    summary: "Reviewed the passage and supporting evidence.",
    strategy: "Textual analysis",
    steps: [
      {
        id: "step-1",
        label: "Examine original passage",
        detail: "Considered John 1:1 within the literary structure of the prologue.",
        status: "supported",
        citations: [0],
        evidence: [
          {
            id: "evidence-1",
            text: "The opening phrase mirrors Genesis 1:1, signaling a creation motif.",
            citationIds: [0],
          },
        ],
        children: [
          {
            id: "step-1a",
            label: "Check cross references",
            detail: "Compared the usage of 'Logos' in other Johannine passages.",
            status: "in_progress",
            evidence: [],
            citations: [],
          },
        ],
      },
      {
        id: "step-2",
        label: "Assess theological claim",
        detail: "Confirmed that the Logos is presented as divine and eternal.",
        outcome: "Claim affirmed",
        status: "complete",
        confidence: 0.9,
        citations: [],
        evidence: [],
      },
    ],
  };

  it("renders reasoning steps with nested structure and status indicators", () => {
    render(<ReasoningTraceComponent trace={sampleTrace} title="Model reasoning" />);

    expect(screen.getByRole("group", { name: "Model reasoning" })).toBeInTheDocument();
    expect(screen.getByText("Reviewed the passage and supporting evidence.")).toBeInTheDocument();
    expect(screen.getByText("Examine original passage")).toBeInTheDocument();
    expect(screen.getByText("Assess theological claim")).toBeInTheDocument();
    expect(screen.getByText("Claim affirmed")).toBeInTheDocument();
    const evidenceList = screen.getByRole("list", { name: "Supporting evidence" });
    expect(
      within(evidenceList).getByText(
        "The opening phrase mirrors Genesis 1:1, signaling a creation motif."
      )
    ).toBeInTheDocument();
    const citationsLine = screen.getByText((content, element) =>
      element?.classList.contains("chat-reasoning-trace__citations") ?? false
    );
    expect(citationsLine).toHaveTextContent(/1/);
    expect(screen.getByText("Check cross references")).toBeInTheDocument();
    expect(screen.getByText("In progress")).toBeInTheDocument();
    expect(screen.getByText("Complete")).toBeInTheDocument();
    const confidenceLine = screen.getByText((content, element) =>
      element?.classList.contains("chat-reasoning-trace__confidence") ?? false
    );
    expect(confidenceLine).toHaveTextContent(/90%/);
  });

  it("returns null when no steps are provided", () => {
    const { container, rerender } = render(<ReasoningTraceComponent trace={null} />);
    expect(container.firstChild).toBeNull();

    rerender(<ReasoningTraceComponent trace={{ summary: "", steps: [] }} />);
    expect(container.firstChild).toBeNull();
  });
});
