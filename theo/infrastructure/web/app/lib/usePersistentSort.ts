"use client";

import { useCallback, useState } from "react";

import { GroupSortKey, isGroupSortKey } from "../search/groupSorting";

const STORAGE_KEY = "theo.search.sort";

export function usePersistentSort(defaultValue: GroupSortKey = "rank"): [
  GroupSortKey,
  (nextKey: GroupSortKey) => void,
] {
  const [value, setValue] = useState<GroupSortKey>(() => {
    if (typeof window === "undefined") {
      return defaultValue;
    }
    const storedValue = window.localStorage.getItem(STORAGE_KEY);
    if (storedValue && isGroupSortKey(storedValue)) {
      return storedValue;
    }
    if (storedValue && !isGroupSortKey(storedValue)) {
      window.localStorage.removeItem(STORAGE_KEY);
    }
    return defaultValue;
  });

  const updateValue = useCallback((nextKey: GroupSortKey) => {
    setValue(nextKey);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, nextKey);
    }
  }, []);

  return [value, updateValue];
}
