/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import SearchPageClient from "../../../app/search/components/SearchPageClient";
import type { SearchFilters } from "../../../app/search/searchParams";
import type { SearchResponse } from "../../../app/search/types";
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
  const submitMock = submitFeedback as jest.MockedFunction<typeof submitFeedback>;
  const originalFetch = global.fetch;

  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("dispatches click feedback with scoring context", async () => {
    submitMock.mockResolvedValue(undefined);

    const initialFilters: SearchFilters = {
      query: "logos",
      osis: "",
      collection: "",
      author: "",
      sourceType: "",
      theologicalTradition: "",
      topicDomain: "",
      collectionFacets: [],
      datasetFacets: [],
      variantFacets: [],
      dateStart: "",
      dateEnd: "",
      includeVariants: false,
      includeDisputed: false,
      preset: "",
    };

    const initialResponse: SearchResponse = {
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
    };

    render(
      <SearchPageClient
        initialFilters={initialFilters}
        initialResponse={initialResponse}
        initialError={null}
        initialReranker="cross-encoder"
        hasInitialSearch
      />,
    );

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

  it("shows a loading indicator while fetching search results", async () => {
    const fetchDeferred = deferred<{
      ok: boolean;
      status: number;
      json: () => Promise<SearchResponse>;
      headers: Headers;
    }>();

    global.fetch = jest.fn().mockReturnValue(fetchDeferred.promise) as unknown as typeof fetch;

    const initialFilters: SearchFilters = {
      query: "",
      osis: "",
      collection: "",
      author: "",
      sourceType: "",
      theologicalTradition: "",
      topicDomain: "",
      collectionFacets: [],
      datasetFacets: [],
      variantFacets: [],
      dateStart: "",
      dateEnd: "",
      includeVariants: false,
      includeDisputed: false,
      preset: "",
    };

    render(
      <SearchPageClient
        initialFilters={initialFilters}
        initialResponse={null}
        initialError={null}
        initialReranker={null}
        hasInitialSearch={false}
      />,
    );

    const queryInput = screen.getByLabelText("Query");
    fireEvent.change(queryInput, { target: { value: "incarnation" } });
    const form = screen.getByRole("form", { name: "Search corpus" });
    fireEvent.submit(form);

    expect(screen.getByRole("status")).toHaveTextContent("Searching.");

    fetchDeferred.resolve({
      ok: true,
      status: 200,
      json: async () => ({ results: [] }),
      headers: new Headers(),
    });

    await waitFor(() => {
      expect(screen.queryByRole("status")).not.toBeInTheDocument();
    });
  });
});

function deferred<T>(): { promise: Promise<T>; resolve: (value: T) => void } {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}
