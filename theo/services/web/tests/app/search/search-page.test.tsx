/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";

import SearchPageClient from "../../../app/search/components/SearchPageClient";
import type { SearchFilters } from "../../../app/search/searchParams";
import { submitFeedback } from "../../../app/lib/telemetry";
import { ToastProvider } from "../../../app/components/Toast";

jest.mock("next/navigation", () => {
  let params = new URLSearchParams("q=logos");
  const createSearchParams = () => ({
    get: (key: string) => params.get(key),
    toString: () => params.toString(),
    has: (key: string) => params.has(key),
    entries: () => params.entries(),
    keys: () => params.keys(),
    values: () => params.values(),
    forEach: (callback: (value: string, key: string) => void) => params.forEach(callback),
    [Symbol.iterator]: () => params[Symbol.iterator](),
  });
  return {
    useRouter: () => ({ replace: jest.fn(), push: jest.fn() }),
    useSearchParams: () => createSearchParams(),
    __setSearchParams: (value: string) => {
      params = new URLSearchParams(value);
    },
  };
});

jest.mock("../../../app/lib/telemetry", () => ({
  emitTelemetry: jest.fn(),
  submitFeedback: jest.fn(),
}));

const { __setSearchParams } = require("next/navigation") as {
  __setSearchParams: (value: string) => void;
};

const setSearchParams = __setSearchParams;

const renderWithToast = (ui: ReactElement) => render(<ToastProvider>{ui}</ToastProvider>);

describe("SearchPageClient feedback", () => {
  const originalFetch = global.fetch;
  const fetchMock = jest.fn();
  const submitMock = submitFeedback as jest.MockedFunction<typeof submitFeedback>;

  beforeEach(() => {
    jest.clearAllMocks();
    fetchMock.mockReset();
    global.fetch = fetchMock as unknown as typeof fetch;
    setSearchParams("");
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("dispatches click feedback with scoring context", async () => {
    submitMock.mockResolvedValue(undefined);

    setSearchParams("q=logos");

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

    renderWithToast(
      <SearchPageClient
        initialFilters={initialFilters}
        initialResults={{
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
            },
          ],
        }}
        initialError={null}
        initialRerankerName="cross-encoder"
        initialHasSearched
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
          confidence: 0.88,
          query: "logos",
        }),
      );
    });
  });

  it("shows a loading indicator while fetching new results", async () => {
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

    let resolveFetch: ((value: Response) => void) | undefined;
    fetchMock.mockImplementation(
      () =>
        new Promise<Response>((resolve) => {
          resolveFetch = resolve;
        }),
    );

    renderWithToast(
      <SearchPageClient
        initialFilters={initialFilters}
        initialResults={null}
        initialError={null}
        initialRerankerName={null}
        initialHasSearched={false}
      />,
    );

    const queryInput = screen.getByLabelText("Query");
    fireEvent.change(queryInput, { target: { value: "logos" } });

    const submitButton = screen.getByRole("button", { name: /Search(?:ing)? corpus/ });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(
        screen
          .getAllByRole("status")
          .some((element) => element.textContent?.trim() === "Searching..."),
      ).toBe(true);
    });

    resolveFetch?.(
      new Response(JSON.stringify({ results: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await waitFor(() => {
      expect(screen.queryByText("Searching...")).not.toBeInTheDocument();
    });
  });

  it("renders trace details in a toast when requested", async () => {
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

    renderWithToast(
      <SearchPageClient
        initialFilters={initialFilters}
        initialResults={null}
        initialError={{ message: "Search failed", traceId: "trace-1234" }}
        initialRerankerName={null}
        initialHasSearched
      />,
    );

    const showDetailsButton = await screen.findByRole("button", { name: "Show details" });
    fireEvent.click(showDetailsButton);

    await waitFor(() => {
      expect(screen.getByText("Trace ID: trace-1234")).toBeInTheDocument();
    });
  });
});
