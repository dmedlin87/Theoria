/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import SearchPage from "../../../app/search/page";
import { submitFeedback } from "../../../app/lib/telemetry";

jest.mock("next/navigation", () => {
  const params = new URLSearchParams("q=logos");
  const searchParams = {
    get: (key: string) => params.get(key),
    toString: () => params.toString(),
    has: (key: string) => params.has(key),
    entries: () => params.entries(),
    keys: () => params.keys(),
    values: () => params.values(),
    forEach: (callback: (value: string, key: string) => void) => params.forEach(callback),
    [Symbol.iterator]: () => params[Symbol.iterator](),
  };
  return {
    useRouter: () => ({ replace: jest.fn(), push: jest.fn() }),
    useSearchParams: () => searchParams,
  };
});

jest.mock("../../../app/lib/telemetry", () => ({
  emitTelemetry: jest.fn(),
  submitFeedback: jest.fn(),
}));

describe("SearchPage feedback", () => {
  const originalFetch = global.fetch;
  const fetchMock = jest.fn();
  const submitMock = submitFeedback as jest.MockedFunction<typeof submitFeedback>;

  beforeEach(() => {
    jest.clearAllMocks();
    fetchMock.mockReset();
    global.fetch = fetchMock as unknown as typeof fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("dispatches click feedback with scoring context", async () => {
    submitMock.mockResolvedValue(undefined);

    const searchResponse = {
      ok: true,
      status: 200,
      json: jest.fn().mockResolvedValue({
        results: [
          {
            id: "passage-1",
            document_id: "doc-1",
            text: "In the beginning",
            snippet: "In the beginning was the Word",
            document_title: "Sample Treatise",
            rank: 0,
            score: 0.92,
            document_score: 0.88,
            document_rank: 0,
            reranker_score: 0.92,
            retriever_score: 0.81,
          },
        ],
      }),
      headers: new Headers({ "x-reranker": "cross-encoder" }),
    } as const;

    fetchMock.mockResolvedValueOnce(searchResponse as unknown as Response);

    render(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByText("Open passage")).toBeInTheDocument();
    });

    expect(screen.getByText("Reranked by cross-encoder")).toBeInTheDocument();

    const link = screen.getByRole("link", { name: "Open passage" });
    fireEvent.click(link);

    await waitFor(() => {
      expect(submitMock).toHaveBeenCalledWith(
        expect.objectContaining({
          action: "click",
          documentId: "doc-1",
          passageId: "passage-1",
          rank: 0,
          score: 0.92,
          confidence: 0.81,
          query: "logos",
        }),
      );
    });
  });
});
