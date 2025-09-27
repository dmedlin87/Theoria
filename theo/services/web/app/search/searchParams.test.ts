import { parseSearchParams, serializeSearchParams } from "./searchParams";

describe("searchParams helpers", () => {
  it("round-trips filters while trimming whitespace", () => {
    const queryString = serializeSearchParams({
      query: "  grace   ",
      osis: "  John.3.16  ",
      collection: "  Gospel Narratives  ",
      author: "   Jane Doe   ",
      sourceType: "  pdf  ",
      collectionFacets: ["  Dead Sea Scrolls  ", "  Nag Hammadi  "],
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
      disputed: "1",
      osis: "John.3.16",
      preset: "scholar",
      q: "grace",
      source_type: "pdf",
      variants: "1",
    });

    const parsed = parseSearchParams(queryString);
    expect(parsed).toEqual({
      query: "grace",
      osis: "John.3.16",
      collection: "Gospel Narratives",
      author: "Jane Doe",
      sourceType: "pdf",
      collectionFacets: ["Dead Sea Scrolls", "Nag Hammadi"],
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
      author: undefined,
      sourceType: "",
      collectionFacets: [],
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
      collectionFacets: [],
      dateStart: "",
      dateEnd: "",
      includeVariants: false,
      includeDisputed: false,
      preset: "",
    });
  });

  it("parses comma-delimited facets and boolean flags", () => {
    const parsed = parseSearchParams(
      "collection_facets=Dead%20Sea%20Scrolls,Gospels&variants=1&disputed=true",
    );

    expect(parsed.collectionFacets).toEqual(["Dead Sea Scrolls", "Gospels"]);
    expect(parsed.includeVariants).toBe(true);
    expect(parsed.includeDisputed).toBe(true);
  });
});
