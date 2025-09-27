/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";

import ReliabilityOverviewCard from "../app/verse/[osis]/ReliabilityOverviewCard";

describe("ReliabilityOverviewCard", () => {
  const baseUrl = "http://127.0.0.1:8000";

  beforeEach(() => {
    jest.resetAllMocks();
    global.fetch = jest.fn();
  });

  it("renders snapshot content for apologetic mode", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        osis: "John.1.1",
        mode: "apologetic",
        consensus: [
          { summary: "Most early teachers see harmony.", citations: ["Source A"] },
        ],
        disputed: [
          { summary: "Some readers point to tension.", citations: ["Source B"] },
        ],
        manuscripts: [
          { summary: "P66 reads the line without an article.", citations: ["NA28"] },
        ],
      }),
      text: async () => "",
    });

    const element = await ReliabilityOverviewCard({ osis: "John.1.1", mode: "apologetic" });
    render(element ?? <></>);

    expect(global.fetch).toHaveBeenCalledWith(
      `${baseUrl}/research/overview?osis=John.1.1&mode=apologetic`,
      { cache: "no-store" },
    );

    expect(screen.getByText("Reliability snapshot")).toBeInTheDocument();
    expect(
      screen.getByText("Apologetic mode highlights harmony and trusted support."),
    ).toBeInTheDocument();
    expect(screen.getByText("Consensus threads")).toBeInTheDocument();
    expect(screen.getByText("Most early teachers see harmony.")).toBeInTheDocument();
    expect(screen.getByText("Sources: Source A")).toBeInTheDocument();
  });

  it("renders empty state when no overview data", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        osis: "John.1.1",
        mode: "apologetic",
        consensus: [],
        disputed: [],
        manuscripts: [],
      }),
      text: async () => "",
    });

    const element = await ReliabilityOverviewCard({ osis: "John.1.1", mode: "apologetic" });
    render(element ?? <></>);

    expect(
      screen.getByText("No overview data is available yet. Add research notes to build this snapshot."),
    ).toBeInTheDocument();
  });

  it("renders error state when overview fails", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      statusText: "Server error",
      text: async () => "Boom",
    });

    const element = await ReliabilityOverviewCard({ osis: "John.1.1", mode: "skeptical" });
    render(element ?? <></>);

    expect(screen.getByRole("alert")).toHaveTextContent("Unable to load the overview. Boom");
  });
});

