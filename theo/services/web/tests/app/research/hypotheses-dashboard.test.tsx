import "@testing-library/jest-dom";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import HypothesesDashboardClient from "../../../app/research/hypotheses/HypothesesDashboardClient";
import type {
  HypothesisFilters,
  HypothesisRecord,
} from "../../../app/research/hypotheses/client";

jest.mock("../../../app/research/hypotheses/client", () => {
  const actual = jest.requireActual("../../../app/research/hypotheses/client");
  return {
    ...actual,
    fetchHypotheses: jest.fn(),
    updateHypothesis: jest.fn(),
  };
});

const { fetchHypotheses, updateHypothesis } = jest.requireMock(
  "../../../app/research/hypotheses/client",
) as {
  fetchHypotheses: jest.Mock;
  updateHypothesis: jest.Mock;
};

const BASE_FILTERS: HypothesisFilters = { statuses: [], query: undefined, minConfidence: undefined };

const SAMPLE_HYPOTHESES: HypothesisRecord[] = [
  {
    id: "hyp-1",
    claim: "Luke depends on eyewitness material",
    confidence: 0.72,
    status: "active",
    trailId: null,
    supportingPassageIds: ["passage-a"],
    contradictingPassageIds: [],
    perspectiveScores: { apologetic: 0.7 },
    metadata: null,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
  {
    id: "hyp-2",
    claim: "Q source preserves sayings",
    confidence: 0.41,
    status: "uncertain",
    trailId: null,
    supportingPassageIds: [],
    contradictingPassageIds: ["passage-b"],
    perspectiveScores: null,
    metadata: null,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
];

describe("HypothesesDashboardClient", () => {
  beforeEach(() => {
    fetchHypotheses.mockReset();
    updateHypothesis.mockReset();
  });

  it("renders hypotheses with status badges", () => {
    render(
      <HypothesesDashboardClient
        initialHypotheses={SAMPLE_HYPOTHESES}
        initialTotal={SAMPLE_HYPOTHESES.length}
        initialFilters={BASE_FILTERS}
      />,
    );

    expect(screen.getByRole("heading", { name: /hypothesis dashboard/i })).toBeVisible();
    expect(screen.getByText(/luke depends on eyewitness material/i)).toBeInTheDocument();
    expect(screen.getByText(/q source preserves sayings/i)).toBeInTheDocument();
    expect(screen.getAllByText(/confidence:/i)).toHaveLength(2);
  });

  it("applies status filters and refreshes the list", async () => {
    fetchHypotheses.mockResolvedValueOnce({ hypotheses: SAMPLE_HYPOTHESES, total: 2 });
    fetchHypotheses.mockResolvedValueOnce({
      hypotheses: [SAMPLE_HYPOTHESES[0]],
      total: 1,
    });

    render(
      <HypothesesDashboardClient
        initialHypotheses={SAMPLE_HYPOTHESES}
        initialTotal={SAMPLE_HYPOTHESES.length}
        initialFilters={BASE_FILTERS}
      />,
    );

    const confirmedButtons = screen.getAllByRole("button", { name: /confirmed/i });
    await userEvent.click(confirmedButtons[0]);

    await waitFor(() => {
      expect(fetchHypotheses).toHaveBeenLastCalledWith({
        ...BASE_FILTERS,
        statuses: ["confirmed"],
      });
    });
  });

  it("updates a hypothesis via actions", async () => {
    updateHypothesis.mockResolvedValue({
      ...SAMPLE_HYPOTHESES[0],
      status: "refuted",
      confidence: 0.05,
    });

    render(
      <HypothesesDashboardClient
        initialHypotheses={SAMPLE_HYPOTHESES}
        initialTotal={SAMPLE_HYPOTHESES.length}
        initialFilters={BASE_FILTERS}
      />,
    );

    const refuteButton = screen.getAllByRole("button", { name: /mark refuted/i })[0];
    await userEvent.click(refuteButton);

    await waitFor(() => {
      expect(updateHypothesis).toHaveBeenCalledWith("hyp-1", {
        status: "refuted",
        confidence: 0.05,
      });
    });

    const card = screen.getByText(/luke depends on eyewitness material/i).closest("article");
    expect(card).not.toBeNull();
    await waitFor(() => {
      expect(card?.textContent?.toLowerCase()).toContain("refuted");
    });
  });
});
