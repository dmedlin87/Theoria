import { sortDocumentGroups } from "./groupSorting";

describe("sortDocumentGroups", () => {
  it("prioritizes ranked groups including rank zero ahead of unranked groups", () => {
    const groups = [
      { documentId: "unranked", title: "Unranked", score: 10, passages: [] },
      { documentId: "rank1", title: "Rank One", rank: 1, score: 5, passages: [] },
      { documentId: "rank0", title: "Rank Zero", rank: 0, score: 2, passages: [] },
      { documentId: "rank2", title: "Rank Two", rank: 2, score: 15, passages: [] },
    ];

    const sorted = sortDocumentGroups(groups);

    expect(sorted.map((group) => group.documentId)).toEqual([
      "rank0",
      "rank1",
      "rank2",
      "unranked",
    ]);
  });
});
