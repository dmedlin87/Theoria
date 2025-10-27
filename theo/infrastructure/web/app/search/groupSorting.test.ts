import {
  getGroupSortComparator,
  rankFirstComparator,
  scoreFirstComparator,
  sortDocumentGroups,
  titleComparator,
} from "./groupSorting";

type TestGroup = {
  documentId: string;
  title: string;
  rank?: number | null;
  score?: number | null;
};

const buildTitles = (groups: TestGroup[]) => groups.map((group) => group.documentId);

describe("group sorting comparators", () => {
  it("sorts by rank first, then score, then title", () => {
    const groups: TestGroup[] = [
      { documentId: "rank2", title: "Gamma", rank: 2, score: 1 },
      { documentId: "rank1-low", title: "Beta", rank: 1, score: 5 },
      { documentId: "rank1-high", title: "Alpha", rank: 1, score: 7 },
      { documentId: "unranked-score", title: "Delta", score: 8 },
      { documentId: "unranked-none", title: "Epsilon" },
    ];

    const sorted = [...groups].sort(rankFirstComparator);

    expect(buildTitles(sorted)).toEqual([
      "rank1-high",
      "rank1-low",
      "rank2",
      "unranked-score",
      "unranked-none",
    ]);
  });

  it("sorts by score descending with alphabetical tie-breaking and nulls last", () => {
    const groups: TestGroup[] = [
      { documentId: "high", title: "Zeta", score: 12 },
      { documentId: "alpha", title: "Alpha", score: 5 },
      { documentId: "beta", title: "Beta", score: 5 },
      { documentId: "no-score", title: "Gamma" },
    ];

    const sorted = [...groups].sort(scoreFirstComparator);

    expect(buildTitles(sorted)).toEqual(["high", "alpha", "beta", "no-score"]);
  });

  it("sorts alphabetically by title", () => {
    const groups: TestGroup[] = [
      { documentId: "gamma", title: "Gamma" },
      { documentId: "alpha", title: "Alpha" },
      { documentId: "beta", title: "Beta" },
    ];

    const sorted = [...groups].sort(titleComparator);

    expect(buildTitles(sorted)).toEqual(["alpha", "beta", "gamma"]);
  });
});

describe("group sorting dispatcher", () => {
  const groups: TestGroup[] = [
    { documentId: "rank2", title: "Gamma", rank: 2, score: 1 },
    { documentId: "rank1", title: "Alpha", rank: 1, score: 7 },
    { documentId: "unranked", title: "Beta", score: 9 },
  ];

  it("returns the requested comparator for known keys", () => {
    const byScore = getGroupSortComparator<TestGroup>("score");
    const sorted = [...groups].sort(byScore);

    expect(buildTitles(sorted)).toEqual(["unranked", "rank1", "rank2"]);
  });

  it("falls back to rank-first comparator for unknown keys", () => {
    const fallbackSorted = sortDocumentGroups(groups, "unknown");
    const expected = [...groups].sort(rankFirstComparator);

    expect(buildTitles(fallbackSorted)).toEqual(buildTitles(expected));
  });

  it("defaults to rank sorting when no key is provided", () => {
    const sorted = sortDocumentGroups(groups);
    const expected = [...groups].sort(rankFirstComparator);

    expect(buildTitles(sorted)).toEqual(buildTitles(expected));
  });
});
