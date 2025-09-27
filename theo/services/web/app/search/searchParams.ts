import type { ReadonlyURLSearchParams } from "next/navigation";

export type SearchFilters = {
  query: string;
  osis: string;
  collection: string;
  author: string;
  sourceType: string;
  collectionFacets: string[];
  dateStart: string;
  dateEnd: string;
  includeVariants: boolean;
  includeDisputed: boolean;
  preset: string;
};

const KEY_MAP: Record<keyof SearchFilters, string> = {
  query: "q",
  osis: "osis",
  collection: "collection",
  author: "author",
  sourceType: "source_type",
  collectionFacets: "collection_facets",
  dateStart: "date_start",
  dateEnd: "date_end",
  includeVariants: "variants",
  includeDisputed: "disputed",
  preset: "preset",
};

function normalizeInput(value: string | undefined | null): string {
  return value?.trim() ?? "";
}

function normalizeList(value: string | undefined | null): string[] {
  const normalized = normalizeInput(value);
  if (!normalized) {
    return [];
  }
  return normalized
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseBoolean(value: string | undefined | null): boolean {
  if (!value) return false;
  const normalized = value.trim().toLowerCase();
  return normalized === "1" || normalized === "true" || normalized === "yes";
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
    collectionFacets: normalizeList(params.get(KEY_MAP.collectionFacets)),
    dateStart: normalizeInput(params.get(KEY_MAP.dateStart)),
    dateEnd: normalizeInput(params.get(KEY_MAP.dateEnd)),
    includeVariants: parseBoolean(params.get(KEY_MAP.includeVariants)),
    includeDisputed: parseBoolean(params.get(KEY_MAP.includeDisputed)),
    preset: normalizeInput(params.get(KEY_MAP.preset)),
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
      return;
    }

    if (Array.isArray(value)) {
      if (value.length > 0) {
        params.set(KEY_MAP[key], value.map((item) => item.trim()).filter(Boolean).join(","));
      }
      return;
    }

    if (typeof value === "boolean") {
      if (value) {
        params.set(KEY_MAP[key], "1");
      }
    }
  });
  return params.toString();
}
