import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useSearchFilters } from "../../../app/search/hooks/useSearchFilters";
import type { SearchFilters } from "../../../app/search/searchParams";

const baseFilters: SearchFilters = {
  query: "  logos ",
  osis: " John.1.1 ",
  collection: "",
  author: "",
  sourceType: "",
  theologicalTradition: "",
  topicDomain: "",
  collectionFacets: ["sermon"],
  datasetFacets: [],
  variantFacets: [],
  dateStart: "",
  dateEnd: "",
  includeVariants: false,
  includeDisputed: false,
  preset: "",
};

describe("useSearchFilters", () => {
  it("trims values when computing currentFilters", () => {
    const { result } = renderHook(() => useSearchFilters(baseFilters));

    expect(result.current.currentFilters.query).toBe("logos");
    expect(result.current.currentFilters.osis).toBe("John.1.1");
    expect(result.current.filters.presetSelection).toBe("custom");
  });

  it("applies provided filters and updates preset selection", () => {
    const { result } = renderHook(() => useSearchFilters(baseFilters));

    act(() => {
      result.current.applyFilters({
        ...baseFilters,
        query: "incarnation",
        preset: "verse-brief",
        collectionFacets: ["study"],
      });
    });

    expect(result.current.filters.query).toBe("incarnation");
    expect(result.current.filters.collectionFacets).toEqual(["study"]);
    expect(result.current.filters.presetSelection).toBe("verse-brief");
  });

  it("resets filters and marks preset as custom", () => {
    const { result } = renderHook(() => useSearchFilters(baseFilters));

    act(() => {
      result.current.setters.setQuery("Trinity");
      result.current.setters.setIncludeVariants(true);
      result.current.toggleFacet("sermon");
      result.current.resetFilters();
    });

    expect(result.current.filters.query).toBe("");
    expect(result.current.filters.includeVariants).toBe(false);
    expect(result.current.filters.collectionFacets).toEqual([]);
    expect(result.current.filters.presetSelection).toBe("custom");
  });

  it("toggles dataset facets and records custom preset selection", () => {
    const { result } = renderHook(() => useSearchFilters(baseFilters));

    act(() => {
      result.current.toggleDatasetFacet("greek");
    });

    expect(result.current.filters.datasetFacets).toEqual(["greek"]);
    expect(result.current.filters.presetSelection).toBe("custom");

    act(() => {
      result.current.toggleDatasetFacet("greek");
    });

    expect(result.current.filters.datasetFacets).toEqual([]);
  });
});
