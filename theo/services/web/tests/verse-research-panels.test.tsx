/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import ContradictionsPanel from "../app/verse/[osis]/ContradictionsPanel";
import GeoPanel from "../app/verse/[osis]/GeoPanel";
import type { ResearchFeatureFlags } from "../app/verse/[osis]/research-panels";

describe("ContradictionsPanel", () => {
  const baseUrl = "http://127.0.0.1:8000";

  beforeEach(() => {
    jest.resetAllMocks();
    global.fetch = jest.fn();
  });

  it("renders contradictions when available", async () => {
    const mockFlags: ResearchFeatureFlags = { research: true, contradictions: true };
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        contradictions: [
          { summary: "Summary", osis: ["Gen.1.1", "Gen.1.2"] },
          { summary: "Another summary", osis: ["Gen.2.1", "Gen.2.2"] },
        ],
      }),
      text: async () => "",
    });

    const element = await ContradictionsPanel({ osis: "Gen.1.1", features: mockFlags });
    render(element ?? <></>);

    expect(global.fetch).toHaveBeenCalledWith(
      `${baseUrl}/research/contradictions?osis=Gen.1.1`,
      { cache: "no-store" },
    );
    expect(screen.getByText("Potential contradictions")).toBeInTheDocument();
    expect(screen.getByText("Summary")).toBeInTheDocument();
    expect(screen.getByText("Gen.1.1 ⇄ Gen.1.2")).toBeInTheDocument();
  });

  it("renders empty state when no contradictions", async () => {
    const mockFlags: ResearchFeatureFlags = { research: true, contradictions: true };
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ contradictions: [] }),
      text: async () => "",
    });

    const element = await ContradictionsPanel({ osis: "Gen.1.1", features: mockFlags });
    render(element ?? <></>);

    expect(screen.getByText("No contradictions found.")).toBeInTheDocument();
  });

  it("renders error state when request fails", async () => {
    const mockFlags: ResearchFeatureFlags = { research: true, contradictions: true };
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      statusText: "Server error",
      text: async () => "Boom",
    });

    const element = await ContradictionsPanel({ osis: "Gen.1.1", features: mockFlags });
    render(element ?? <></>);

    expect(screen.getByRole("alert")).toHaveTextContent("Unable to load contradictions. Boom");
  });

  it("returns null when contradictions feature disabled", async () => {
    const mockFlags: ResearchFeatureFlags = { research: true, contradictions: false };
    const element = await ContradictionsPanel({ osis: "Gen.1.1", features: mockFlags });
    expect(element).toBeNull();
  });
});

describe("GeoPanel", () => {
  beforeEach(() => {
    jest.resetAllMocks();
    global.fetch = jest.fn();
  });

  it("renders search results", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        results: [
          {
            name: "Jerusalem",
            osis: "Josh.10.1",
            coordinates: { lat: 31.78, lng: 35.21 },
            aliases: ["Jebus"],
          },
        ],
      }),
      text: async () => "",
    });

    render(<GeoPanel osis="Gen.1.1" features={{ research: true, geo: true }} />);

    fireEvent.change(screen.getByLabelText(/Search locations/i), { target: { value: "Jerusalem" } });
    fireEvent.click(screen.getByRole("button", { name: /search/i }));

    await waitFor(() => {
      expect(screen.getByText("Jerusalem")).toBeInTheDocument();
      expect(screen.getByText(/Coordinates:/i)).toHaveTextContent("31.78, 35.21");
      expect(screen.getByText(/Also known as/)).toHaveTextContent("Jebus");
    });

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/research/geo/search"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ query: "Jerusalem", osis: "Gen.1.1" }),
      }),
    );
  });

  it("renders empty state when no results", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ results: [] }),
      text: async () => "",
    });

    render(<GeoPanel osis="Gen.1.1" features={{ research: true, geo: true }} />);

    fireEvent.change(screen.getByLabelText(/Search locations/i), { target: { value: "Nineveh" } });
    fireEvent.click(screen.getByRole("button", { name: /search/i }));

    await waitFor(() => {
      expect(screen.getByText("No locations found.")).toBeInTheDocument();
    });
  });

  it("renders error state when search fails", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      statusText: "Server error",
      text: async () => "Geo failure",
    });

    render(<GeoPanel osis="Gen.1.1" features={{ research: true, geo: true }} />);

    fireEvent.change(screen.getByLabelText(/Search locations/i), { target: { value: "Bethel" } });
    fireEvent.click(screen.getByRole("button", { name: /search/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Geo failure");
    });
  });

  it("does not render when geo feature disabled", () => {
    const { container } = render(<GeoPanel osis="Gen.1.1" features={{ research: true, geo: false }} />);
    expect(container.firstChild).toBeNull();
  });
});
