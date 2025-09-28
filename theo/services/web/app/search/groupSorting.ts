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
  const aRank = typeof a.rank === "number" ? a.rank : null;
  const bRank = typeof b.rank === "number" ? b.rank : null;

  if (aRank !== null && bRank !== null) {
    const rankDifference = aRank - bRank;
    if (rankDifference !== 0) {
      return rankDifference;
    }
    return scoreFirstComparator(a, b);
  }

  if (aRank !== null) return -1;
  if (bRank !== null) return 1;

  return scoreFirstComparator(a, b);
};

export type GroupSortKey = "rank" | "score" | "title";

const COMPARATORS: Record<GroupSortKey, GroupComparator<SortableDocumentGroup>> = {
  rank: rankFirstComparator,
  score: scoreFirstComparator,
  title: titleComparator,
};

export function isGroupSortKey(value: unknown): value is GroupSortKey {
  return typeof value === "string" && value in COMPARATORS;
}

const withGenericComparator = <T extends SortableDocumentGroup>(
  comparator: GroupComparator<SortableDocumentGroup>
): GroupComparator<T> => (a, b) => comparator(a, b);

export function getGroupSortComparator<T extends SortableDocumentGroup>(
  key: string | null | undefined
): GroupComparator<T> {
  const fallbackKey: GroupSortKey = "rank";
  const comparator = isGroupSortKey(key)
    ? COMPARATORS[key]
    : COMPARATORS[fallbackKey];

  return withGenericComparator<T>(comparator);
}

export function sortDocumentGroups<T extends SortableDocumentGroup>(
  groups: T[],
  key?: string | null
): T[] {
  const comparator = getGroupSortComparator<T>(key);
  return [...groups].sort(comparator);
}
