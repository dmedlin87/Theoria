import type { ReadonlyURLSearchParams } from "next/navigation";

export type SearchFilters = {
  query: string;
  osis: string;
  collection: string;
  author: string;
  sourceType: string;
  dataset: string;
  variant: string;
};

const KEY_MAP: Record<keyof SearchFilters, string> = {
  query: "q",
  osis: "osis",
  collection: "collection",
  author: "author",
  sourceType: "source_type",
  dataset: "dataset",
  variant: "variant",
};

function normalizeInput(value: string | undefined | null): string {
  return value?.trim() ?? "";
}

function createSearchParams(input: string | URLSearchParams | ReadonlyURLSearchParams): URLSearchParams {
  if (typeof input === "string") {
    const query = input.startsWith("?") ? input.slice(1) : input;
    return new URLSearchParams(query);
  }
  return new URLSearchParams(input.toString());
}

export function parseSearchParams(
  source?: string | URLSearchParams | ReadonlyURLSearchParams | null,
): SearchFilters {
  const params = source ? createSearchParams(source) : new URLSearchParams();
  return {
    query: normalizeInput(params.get(KEY_MAP.query)),
    osis: normalizeInput(params.get(KEY_MAP.osis)),
    collection: normalizeInput(params.get(KEY_MAP.collection)),
    author: normalizeInput(params.get(KEY_MAP.author)),
    sourceType: normalizeInput(params.get(KEY_MAP.sourceType)),
    dataset: normalizeInput(params.get(KEY_MAP.dataset)),
    variant: normalizeInput(params.get(KEY_MAP.variant)),
  };
}

export function serializeSearchParams(filters: Partial<SearchFilters>): string {
  const params = new URLSearchParams();
  (Object.keys(KEY_MAP) as Array<keyof SearchFilters>).forEach((key) => {
    const value = filters[key];
    if (typeof value === "string") {
      const trimmed = value.trim();
      if (trimmed) {
        params.set(KEY_MAP[key], trimmed);
      }
    }
  });
  return params.toString();
}
