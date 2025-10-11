import { parseSearchParams, serializeSearchParams } from "./searchParams";

jest.mock("next/link", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
}));

describe("searchParams helpers", () => {
  it("round-trips filters while trimming whitespace", () => {
    const queryString = serializeSearchParams({
      query: "  grace   ",
      osis: "  John.3.16  ",
      collection: "  Gospel Narratives  ",
      author: "   Jane Doe   ",
      sourceType: "  pdf  ",
      theologicalTradition: "  catholic  ",
      topicDomain: "  christology  ",
      collectionFacets: ["  Dead Sea Scrolls  ", "  Nag Hammadi  "],
      datasetFacets: ["  dss  "],
      variantFacets: ["  disputed  ", "  harmonized  "],
      dateStart: " 0100-01-01 ",
      dateEnd: " 0200-12-31 ",
      includeVariants: true,
      includeDisputed: true,
      preset: " scholar ",
    });

    expect(Object.fromEntries(new URLSearchParams(queryString))).toEqual({
      author: "Jane Doe",
      collection_facets: "Dead Sea Scrolls,Nag Hammadi",
      collection: "Gospel Narratives",
      date_end: "0200-12-31",
      date_start: "0100-01-01",
      dataset: "dss",
      disputed: "1",
      variant: "disputed,harmonized",
      osis: "John.3.16",
      preset: "scholar",
      q: "grace",
      source_type: "pdf",
      theological_tradition: "catholic",
      topic_domain: "christology",
      variants: "1",
    });

    const parsed = parseSearchParams(queryString);
    expect(parsed).toEqual({
      query: "grace",
      osis: "John.3.16",
      collection: "Gospel Narratives",
      author: "Jane Doe",
      sourceType: "pdf",
      theologicalTradition: "catholic",
      topicDomain: "christology",
      collectionFacets: ["Dead Sea Scrolls", "Nag Hammadi"],
      datasetFacets: ["dss"],
      variantFacets: ["disputed", "harmonized"],
      dateStart: "0100-01-01",
      dateEnd: "0200-12-31",
      includeVariants: true,
      includeDisputed: true,
      preset: "scholar",
    });
  });

  it("omits empty filters from serialization", () => {
    const queryString = serializeSearchParams({
      query: "",
      osis: "  ",
      collection: "Gospels",
      sourceType: "",
      collectionFacets: [],
      datasetFacets: [],
      variantFacets: [],
      includeVariants: false,
    });

    expect(queryString).toBe("collection=Gospels");
  });

  it("parses missing filters as empty strings", () => {
    expect(parseSearchParams(undefined)).toEqual({
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
    });
  });

  it("parses comma-delimited facets and boolean flags", () => {
    const parsed = parseSearchParams(
      "collection_facets=Dead%20Sea%20Scrolls,Gospels&dataset=dss&variant=disputed,archaeology&variants=1&disputed=true",
    );

    expect(parsed.collectionFacets).toEqual(["Dead Sea Scrolls", "Gospels"]);
    expect(parsed.datasetFacets).toEqual(["dss"]);
    expect(parsed.variantFacets).toEqual(["disputed", "archaeology"]);
    expect(parsed.includeVariants).toBe(true);
    expect(parsed.includeDisputed).toBe(true);
  });

  describe("normalizeStringArray", () => {
    let normalizeStringArray: (value: unknown) => string[];

    beforeAll(async () => {
      ({ normalizeStringArray } = await import("./components/SearchPageClient"));
    });

    it("filters non-string entries from arrays", () => {
      const mixedValues = [
        "  Alpha  ",
        123,
        null,
        undefined,
        "Beta",
        { label: "Gamma" },
        "",
      ] as unknown[];

      expect(normalizeStringArray(mixedValues)).toEqual(["Alpha", "Beta"]);
    });

    it("returns empty arrays for non-array non-string inputs", () => {
      expect(normalizeStringArray(42)).toEqual([]);
      expect(normalizeStringArray({ bad: "data" })).toEqual([]);
    });
  });
});
