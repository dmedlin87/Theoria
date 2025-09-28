/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";

import CommentariesPanel from "../app/verse/[osis]/CommentariesPanel";
import ContradictionsPanel from "../app/verse/[osis]/ContradictionsPanel";
import CrossReferencesPanel from "../app/verse/[osis]/CrossReferencesPanel";
import GeoPanel from "../app/verse/[osis]/GeoPanel";
import MorphologyPanel from "../app/verse/[osis]/MorphologyPanel";
import TextualVariantsPanel from "../app/verse/[osis]/TextualVariantsPanel";
import { ModeProvider } from "../app/context/ModeContext";
import ResearchPanels, {
  type ResearchFeatureFlags,
} from "../app/verse/[osis]/research-panels";

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
          {
            summary: "Summary",
            osis: ["Gen.1.1", "Gen.1.2"],
            severity: "high",
            sources: [
              { label: "Skeptical commentary", url: "https://example.com/contradiction" },
            ],
            snippet_pairs: [
              {
                left: { osis: "Gen.1.1", text: "In the beginning God created" },
                right: { osis: "Gen.1.2", text: "The earth was without form" },
              },
            ],
          },
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
    expect(screen.getByText("Severity: High")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Skeptical commentary" }),
    ).toHaveAttribute("href", "https://example.com/contradiction");
    expect(
      screen.getByRole("link", { name: "Skeptical commentary" }),
    ).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getAllByText("Open verse").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/In the beginning God created/)).toBeInTheDocument();
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

  it("allows toggling visibility for Apologetic mode", async () => {
    const mockFlags: ResearchFeatureFlags = { research: true, contradictions: true };
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        contradictions: [
          {
            summary: "Summary",
            osis: ["Gen.1.1", "Gen.1.2"],
            severity: "medium",
          },
        ],
      }),
      text: async () => "",
    });

    const element = await ContradictionsPanel({ osis: "Gen.1.1", features: mockFlags });
    render(element ?? <></>);

    fireEvent.change(screen.getByLabelText("Select viewing mode"), {
      target: { value: "apologetic" },
    });

    await waitFor(() => {
      expect(screen.getByTestId("contradictions-apologetic-hidden")).toBeInTheDocument();
    });

    fireEvent.click(
      screen.getByLabelText(/Show contradictions in Apologetic mode/i),
    );

    await waitFor(() => {
      expect(screen.queryByTestId("contradictions-apologetic-hidden")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Severity: Medium")).toBeInTheDocument();
  });

  it("returns null when contradictions feature disabled", async () => {
    const mockFlags: ResearchFeatureFlags = { research: true, contradictions: false };
    const element = await ContradictionsPanel({ osis: "Gen.1.1", features: mockFlags });
    expect(element).toBeNull();
  });
});

describe("GeoPanel", () => {
  const baseUrl = "http://127.0.0.1:8000";

  beforeEach(() => {
    jest.resetAllMocks();
    global.fetch = jest.fn();
  });

  it("renders search results", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        items: [
          {
            name: "Jerusalem",
            lat: 31.78,
            lng: 35.21,
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
      `${baseUrl}/research/geo/search?query=Jerusalem`,
      { method: "GET" },
    );
  });

  it("renders empty state when no results", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ items: [] }),
      text: async () => "",
    });

    render(<GeoPanel osis="Gen.1.1" features={{ research: true, geo: true }} />);

    fireEvent.change(screen.getByLabelText(/Search locations/i), { target: { value: "Nineveh" } });
    fireEvent.click(screen.getByRole("button", { name: /search/i }));

    await waitFor(() => {
      expect(screen.getByText("No locations found.")).toBeInTheDocument();
    });
  });

  it("normalizes legacy payloads", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        results: [
          {
            name: "Hebron",
            coordinates: { lat: 31.53, lng: 35.09 },
            aliases: ["Kiriath-arba"],
          },
        ],
      }),
      text: async () => "",
    });

    render(<GeoPanel osis="Gen.23.2" features={{ research: true, geo: true }} />);

    fireEvent.change(screen.getByLabelText(/Search locations/i), { target: { value: "Hebron" } });
    fireEvent.click(screen.getByRole("button", { name: /search/i }));

    await waitFor(() => {
      expect(screen.getByText("Hebron")).toBeInTheDocument();
      expect(screen.getByText(/Coordinates:/i)).toHaveTextContent("31.53, 35.09");
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

describe("CrossReferencesPanel", () => {
  const baseUrl = "http://127.0.0.1:8000";

  beforeEach(() => {
    jest.resetAllMocks();
    global.fetch = jest.fn();
  });

  it("renders cross references", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        osis: "Gen.1.1",
        results: [
          {
            source: "Gen.1.1",
            target: "John.1.1",
            summary: "Creation echoes",
            relation_type: "thematic",
            weight: 0.9,
            dataset: "starter",
          },
        ],
      }),
      text: async () => "",
    });

    const element = await CrossReferencesPanel({
      osis: "Gen.1.1",
      features: { research: true, cross_references: true },
    });
    render(element ?? <></>);

    expect(global.fetch).toHaveBeenCalledWith(
      `${baseUrl}/research/crossrefs?osis=Gen.1.1`,
      { cache: "no-store" },
    );
    expect(screen.getByText("Cross-references")).toBeInTheDocument();
    expect(screen.getByText(/John.1.1/)).toBeInTheDocument();
    expect(screen.getByText(/Creation echoes/)).toBeInTheDocument();
  });

  it("renders empty state when no items", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ osis: "Gen.1.1", results: [] }),
      text: async () => "",
    });

    const element = await CrossReferencesPanel({
      osis: "Gen.1.1",
      features: { research: true, cross_references: true },
    });
    render(element ?? <></>);

    expect(screen.getByText("No cross-references available.")).toBeInTheDocument();
  });

  it("shows error when request fails", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      statusText: "Server error",
      text: async () => "Boom",
    });

    const element = await CrossReferencesPanel({
      osis: "Gen.1.1",
      features: { research: true, cross_references: true },
    });
    render(element ?? <></>);

    expect(screen.getByRole("alert")).toHaveTextContent("Unable to load cross-references. Boom");
  });

  it("returns null when feature disabled", async () => {
    const element = await CrossReferencesPanel({
      osis: "Gen.1.1",
      features: { research: true, cross_references: false },
    });
    expect(element).toBeNull();
  });
});

describe("TextualVariantsPanel", () => {
  const baseUrl = "http://127.0.0.1:8000";

  beforeEach(() => {
    jest.resetAllMocks();
    global.fetch = jest.fn();
  });

  function renderWithMode(
    ui: ReactElement,
    mode: "neutral" | "apologetic" | "skeptical" = "neutral",
  ) {
    return render(<ModeProvider value={mode}>{ui}</ModeProvider>);
  }

  it("renders variant readings with metadata and summary", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        osis: "Gen.1.1",
        readings: [
          {
            id: "r1",
            osis: "Gen.1.1",
            category: "manuscript",
            reading: "Ἐν ἀρχῇ",
            note: "Mainstream reading",
            witness: "P66",
            disputed: false,
            confidence: 0.85,
            witness_metadata: { name: "Papyrus 66", date: "c. 200 CE" },
          },
          {
            id: "r2",
            osis: "Gen.1.1",
            category: "manuscript",
            reading: "Ἐν ἀρχῇ ὁ Θεός",
            note: "Alternative reading",
            witness: "Codex X",
            disputed: true,
            confidence: 0.35,
            witness_metadata: { name: "Codex X", date: "4th c. CE" },
          },
        ],
      }),
      text: async () => "",
    });

    renderWithMode(
      <TextualVariantsPanel
        osis="Gen.1.1"
        features={{ research: true, textual_variants: true }}
      />,
      "apologetic",
    );

    expect(screen.getByText("Loading textual variants…")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Papyrus 66")).toBeInTheDocument();
    });

    expect(global.fetch).toHaveBeenCalledWith(
      `${baseUrl}/research/variants?osis=Gen.1.1`,
      expect.objectContaining({
        cache: "no-store",
        signal: expect.any(AbortSignal),
      }),
    );
    expect(screen.getByText("Mainstream vs. competing readings")).toBeInTheDocument();
    expect(screen.getByText(/Papyrus 66/)).toBeInTheDocument();
    expect(screen.getByText(/Alternative reading/)).toBeInTheDocument();
    expect(screen.getByText("Disputed")).toBeInTheDocument();
  });

  it("renders empty state when no readings", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ osis: "Gen.1.1", readings: [] }),
      text: async () => "",
    });

    renderWithMode(
      <TextualVariantsPanel
        osis="Gen.1.1"
        features={{ research: true, textual_variants: true }}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("No textual variants available.")).toBeInTheDocument();
    });
  });

  it("renders error state when request fails", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      statusText: "Server error",
      text: async () => "Boom",
    });

    renderWithMode(
      <TextualVariantsPanel
        osis="Gen.1.1"
        features={{ research: true, textual_variants: true }}
      />,
    );

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Unable to load textual variants. Boom",
      );
    });
  });

  it("returns null when feature disabled", () => {
    const { container } = renderWithMode(
      <TextualVariantsPanel
        osis="Gen.1.1"
        features={{ research: true, textual_variants: false }}
      />,
    );
    expect(global.fetch).not.toHaveBeenCalled();
    expect(container).toBeEmptyDOMElement();
  });
});

describe("MorphologyPanel", () => {
  const baseUrl = "http://127.0.0.1:8000";

  beforeEach(() => {
    jest.resetAllMocks();
    global.fetch = jest.fn();
  });

  it("renders morphology tokens", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        osis: "Gen.1.1",
        tokens: [
          {
            osis: "Gen.1.1",
            surface: "בְּרֵאשִׁית",
            lemma: "רֵאשִׁית",
            morph: "noun",
            gloss: "beginning",
            position: 1,
          },
        ],
      }),
      text: async () => "",
    });

    const element = await MorphologyPanel({
      osis: "Gen.1.1",
      features: { research: true, morphology: true },
    });
    render(element ?? <></>);

    expect(global.fetch).toHaveBeenCalledWith(
      `${baseUrl}/research/morphology?osis=Gen.1.1`,
      { cache: "no-store" },
    );
    expect(screen.getByText("בְּרֵאשִׁית")).toBeInTheDocument();
    expect(screen.getByText("רֵאשִׁית")).toBeInTheDocument();
  });

  it("renders empty state when no tokens", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ osis: "Gen.1.1", tokens: [] }),
      text: async () => "",
    });

    const element = await MorphologyPanel({
      osis: "Gen.1.1",
      features: { research: true, morphology: true },
    });
    render(element ?? <></>);

    expect(screen.getByText("No morphology tokens available.")).toBeInTheDocument();
  });

  it("renders error state when request fails", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      statusText: "Server error",
      text: async () => "Boom",
    });

    const element = await MorphologyPanel({
      osis: "Gen.1.1",
      features: { research: true, morphology: true },
    });
    render(element ?? <></>);

    expect(screen.getByRole("alert")).toHaveTextContent("Unable to load morphology. Boom");
  });

  it("returns null when feature disabled", async () => {
    const element = await MorphologyPanel({
      osis: "Gen.1.1",
      features: { research: true, morphology: false },
    });
    expect(element).toBeNull();
  });
});

describe("CommentariesPanel", () => {
  const baseUrl = "http://127.0.0.1:8000";

  beforeEach(() => {
    jest.resetAllMocks();
    global.fetch = jest.fn();
  });

  it("renders notes", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        osis: "Gen.1.1",
        notes: [
          {
            id: "note-1",
            title: "Creation prologue",
            body: "Commentary body",
            stance: "apologetic",
            claim_type: "theological",
            confidence: 0.8,
            tags: ["creation"],
            evidences: [
              {
                id: "ev-1",
                source_type: "crossref",
                source_ref: "John.1.1",
                snippet: "In the beginning was the Word",
                osis_refs: ["John.1.1"],
              },
            ],
          },
        ],
      }),
      text: async () => "",
    });

    const element = await CommentariesPanel({
      osis: "Gen.1.1",
      features: { research: true, commentaries: true },
    });
    render(element ?? <></>);

    expect(global.fetch).toHaveBeenCalledWith(
      `${baseUrl}/research/notes?osis=Gen.1.1`,
      { cache: "no-store" },
    );
    expect(screen.getByText("Creation prologue")).toBeInTheDocument();
    expect(screen.getByText(/In the beginning was the Word/)).toBeInTheDocument();
  });

  it("renders empty state when no notes", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ osis: "Gen.1.1", notes: [] }),
      text: async () => "",
    });

    const element = await CommentariesPanel({
      osis: "Gen.1.1",
      features: { research: true, commentaries: true },
    });
    render(element ?? <></>);

    expect(screen.getByText("No commentaries recorded yet.")).toBeInTheDocument();
  });

  it("renders error state when request fails", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      statusText: "Server error",
      text: async () => "Boom",
    });

    const element = await CommentariesPanel({
      osis: "Gen.1.1",
      features: { research: true, commentaries: true },
    });
    render(element ?? <></>);

    expect(screen.getByRole("alert")).toHaveTextContent("Unable to load commentaries. Boom");
  });

  it("returns null when feature disabled", async () => {
    const element = await CommentariesPanel({
      osis: "Gen.1.1",
      features: { research: true, commentaries: false },
    });
    expect(element).toBeNull();
  });
});

describe("ResearchPanels", () => {
  it("returns null when research feature disabled", () => {
    const { container } = render(<ResearchPanels osis="Gen.1.1" features={{ research: false }} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders empty message when no panel features enabled", () => {
    const { getByText } = render(<ResearchPanels osis="Gen.1.1" features={{ research: true }} />);
    expect(
      getByText("No research panels are available for this verse yet."),
    ).toBeInTheDocument();
  });
});
