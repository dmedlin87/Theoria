import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useSearchFilters } from "../../../app/search/hooks/useSearchFilters";
import type { SearchFilters } from "../../../app/search/searchParams";

const BASE_FILTERS: SearchFilters = {
  query: " Gospel ",
  osis: " John.1.1 ",
  collection: " Sermons ",
  author: " Doe ",
  sourceType: "pdf",
  theologicalTradition: " Anglican ",
  topicDomain: " Christology ",
  collectionFacets: ["Dead Sea Scrolls"],
  datasetFacets: ["dss"],
  variantFacets: ["disputed"],
  dateStart: " 1990 ",
  dateEnd: " 2024 ",
  includeVariants: true,
  includeDisputed: false,
  preset: "investigative",
};

describe("useSearchFilters", () => {
  it("normalises current filters for submissions", () => {
    const { result } = renderHook(() => useSearchFilters(BASE_FILTERS));
    expect(result.current.currentFilters).toMatchObject({
      query: "Gospel",
      osis: "John.1.1",
      collection: "Sermons",
      author: "Doe",
      preset: "investigative",
    });
  });

  it("can apply a new filter payload", () => {
    const { result } = renderHook(() => useSearchFilters(BASE_FILTERS));

    act(() => {
      result.current.applyFilters({
        ...BASE_FILTERS,
        query: "Variants",
        includeVariants: false,
        preset: "",
      });
    });

    expect(result.current.filters.query).toBe("Variants");
    expect(result.current.filters.includeVariants).toBe(false);
    expect(result.current.filters.presetSelection).toBe("custom");
  });

  it("resets filters back to defaults", () => {
    const { result } = renderHook(() => useSearchFilters(BASE_FILTERS));

    act(() => {
      result.current.resetFilters();
    });

    expect(result.current.filters.query).toBe("");
    expect(result.current.filters.collectionFacets).toEqual([]);
    expect(result.current.filters.presetSelection).toBe("custom");
  });

  it("toggles dataset facets and marks preset selection as custom", () => {
    const { result } = renderHook(() => useSearchFilters(BASE_FILTERS));

    act(() => {
      result.current.toggleDatasetFacet("nag-hammadi");
    });

    expect(result.current.filters.datasetFacets).toContain("nag-hammadi");
    expect(result.current.filters.presetSelection).toBe("custom");
  });
});
