import { parseSearchParams, serializeSearchParams } from "./searchParams";

describe("searchParams helpers", () => {
  it("round-trips filters while trimming whitespace", () => {
    const queryString = serializeSearchParams({
      query: "  grace   ",
      osis: "  John.3.16  ",
      collection: "  Gospel Narratives  ",
      author: "   Jane Doe   ",
      sourceType: "  pdf  ",
    });

    expect(Object.fromEntries(new URLSearchParams(queryString))).toEqual({
      author: "Jane Doe",
      collection: "Gospel Narratives",
      osis: "John.3.16",
      q: "grace",
      source_type: "pdf",
    });

    const parsed = parseSearchParams(queryString);
    expect(parsed).toEqual({
      query: "grace",
      osis: "John.3.16",
      collection: "Gospel Narratives",
      author: "Jane Doe",
      sourceType: "pdf",
    });
  });

  it("omits empty filters from serialization", () => {
    const queryString = serializeSearchParams({
      query: "",
      osis: "  ",
      collection: "Gospels",
      author: undefined,
      sourceType: "",
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
    });
  });
});
