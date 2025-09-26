export type SortableDocumentGroup = {
  title: string;
  rank?: number | null;
  score?: number | null;
};

export function sortDocumentGroups<T extends SortableDocumentGroup>(groups: T[]): T[] {
  return [...groups].sort((a, b) => {
    const aHasRank = typeof a.rank === "number";
    const bHasRank = typeof b.rank === "number";
    if (aHasRank && bHasRank) {
      return (a.rank as number) - (b.rank as number);
    }
    if (aHasRank) return -1;
    if (bHasRank) return 1;
    if (typeof b.score === "number" && typeof a.score === "number") {
      return b.score - a.score;
    }
    return a.title.localeCompare(b.title);
  });
}
