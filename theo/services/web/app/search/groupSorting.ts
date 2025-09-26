export type SortableDocumentGroup = {
  title: string;
  rank?: number | null;
  score?: number | null;
};

export type GroupComparator<T extends SortableDocumentGroup> = (a: T, b: T) => number;

export const titleComparator = <T extends SortableDocumentGroup>(a: T, b: T): number => {
  return a.title.localeCompare(b.title);
};

export const scoreFirstComparator = <T extends SortableDocumentGroup>(a: T, b: T): number => {
  const aScore = typeof a.score === "number" ? a.score : null;
  const bScore = typeof b.score === "number" ? b.score : null;

  if (aScore !== null && bScore !== null) {
    const scoreDifference = bScore - aScore;
    if (scoreDifference !== 0) {
      return scoreDifference;
    }
  }

  if (aScore !== null && bScore === null) return -1;
  if (aScore === null && bScore !== null) return 1;

  return titleComparator(a, b);
};

export const rankFirstComparator = <T extends SortableDocumentGroup>(a: T, b: T): number => {
  const aHasRank = typeof a.rank === "number";
  const bHasRank = typeof b.rank === "number";

  if (aHasRank && bHasRank) {
    const rankDifference = (a.rank as number) - (b.rank as number);
    if (rankDifference !== 0) {
      return rankDifference;
    }
    return scoreFirstComparator(a, b);
  }

  if (aHasRank) return -1;
  if (bHasRank) return 1;

  return scoreFirstComparator(a, b);
};

const COMPARATORS = {
  rank: rankFirstComparator,
  score: scoreFirstComparator,
  title: titleComparator,
} as const;

export type GroupSortKey = keyof typeof COMPARATORS;

export function isGroupSortKey(value: unknown): value is GroupSortKey {
  return typeof value === "string" && value in COMPARATORS;
}

export function getGroupSortComparator<T extends SortableDocumentGroup>(
  key: string | null | undefined
): GroupComparator<T> {
  const fallbackKey: GroupSortKey = "rank";
  if (isGroupSortKey(key)) {
    return COMPARATORS[key] as GroupComparator<T>;
  }
  return COMPARATORS[fallbackKey] as GroupComparator<T>;
}

export function sortDocumentGroups<T extends SortableDocumentGroup>(
  groups: T[],
  key?: string | null
): T[] {
  const comparator = getGroupSortComparator<T>(key);
  return [...groups].sort(comparator);
}
