import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

import NotebookPage from "../../../app/notebooks/[id]/page";
import { fetchResearchFeatures } from "../../../app/research/features";

jest.mock("next/link", () => ({
  __esModule: true,
  default: ({ children, href }: { children: ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

jest.mock("../../../app/lib/api", () => ({
  getApiBaseUrl: () => "https://example.com",
}));

jest.mock("../../../app/components/NotebookRealtimeListener", () => ({
  __esModule: true,
  default: () => <div data-testid="realtime-listener" />,
}));

jest.mock("../../../app/components/DeliverableExportAction", () => ({
  __esModule: true,
  default: () => <div data-testid="deliverable-export" />,
}));

jest.mock("../../../app/research/features", () => ({
  fetchResearchFeatures: jest.fn(),
}));

describe("NotebookPage", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders entries even when research feature discovery fails", async () => {
    const mockFetch = jest.fn();
    global.fetch = mockFetch as unknown as typeof fetch;

    const notebookResponse = {
      id: "notebook-1",
      title: "Sermon Prep",
      description: "Notes for the upcoming series.",
      team_id: null,
      is_public: true,
      created_by: "alice",
      created_at: new Date("2024-01-01T12:00:00Z").toISOString(),
      updated_at: new Date("2024-01-02T12:00:00Z").toISOString(),
      primary_osis: "John.3.16",
      entry_count: 1,
      entries: [
        {
          id: "entry-1",
          notebook_id: "notebook-1",
          document_id: null,
          osis_ref: "John.3.16",
          content: "God so loved the world...",
          created_by: "alice",
          created_at: new Date("2024-01-01T12:00:00Z").toISOString(),
          updated_at: new Date("2024-01-01T12:30:00Z").toISOString(),
          mentions: [],
        },
      ],
      collaborators: [],
    };

    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => notebookResponse,
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ version: 1 }),
    });

    const consoleErrorSpy = jest.spyOn(console, "error").mockImplementation(() => undefined);

    const mockFetchFeatures = fetchResearchFeatures as jest.MockedFunction<
      typeof fetchResearchFeatures
    >;
    mockFetchFeatures.mockRejectedValueOnce(new Error("discovery offline"));

    const page = await NotebookPage({ params: { id: "notebook-1" } });
    render(page);

    expect(screen.getByText("Entries (1)")).toBeInTheDocument();
    expect(screen.getByText("God so loved the world...")).toBeInTheDocument();
    expect(screen.getByText(/Research features are temporarily unavailable/)).toBeInTheDocument();
    expect(screen.queryByText("Verse Aggregator")).not.toBeInTheDocument();

    expect(consoleErrorSpy).toHaveBeenCalled();

    consoleErrorSpy.mockRestore();
  });
});
