/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { render } from "@testing-library/react";

import SearchPageClient from "../../../app/search/components/SearchPageClient";
import { ToastProvider } from "../../../app/components/Toast";
import type { SearchFilters } from "../../../app/search/searchParams";

jest.mock("next/navigation", () => {
  const params = new URLSearchParams();
  return {
    useRouter: () => ({ replace: jest.fn(), push: jest.fn() }),
    useSearchParams: () => ({
      get: (key: string) => params.get(key),
      toString: () => params.toString(),
      has: (key: string) => params.has(key),
      entries: () => params.entries(),
      keys: () => params.keys(),
      values: () => params.values(),
      forEach: (callback: (value: string, key: string) => void) => params.forEach(callback),
      [Symbol.iterator]: () => params[Symbol.iterator](),
    }),
  };
});

jest.mock("../../../app/lib/telemetry", () => ({
  emitTelemetry: jest.fn(),
  submitFeedback: jest.fn(),
}));

const EMPTY_FILTERS: SearchFilters = {
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

describe("SearchPageClient empty state", () => {
  it("renders the first-run panel when no search has been issued", () => {
    const { asFragment } = render(
      <ToastProvider>
        <SearchPageClient
          initialFilters={EMPTY_FILTERS}
          initialResults={null}
          initialError={null}
          initialRerankerName={null}
          initialHasSearched={false}
        />
      </ToastProvider>,
    );

    expect(asFragment()).toMatchSnapshot();
  });
});
