import type { ReadonlyURLSearchParams } from "next/navigation";

export type SearchFilters = {
  query: string;
  osis: string;
  collection: string;
  author: string;
  sourceType: string;
  theologicalTradition: string;
  topicDomain: string;
  collectionFacets: string[];
  datasetFacets: string[];
  variantFacets: string[];
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
  theologicalTradition: "theological_tradition",
  topicDomain: "topic_domain",
  collectionFacets: "collection_facets",
  datasetFacets: "dataset",
  variantFacets: "variant",
  dateStart: "date_start",
  dateEnd: "date_end",
  includeVariants: "variants",
  includeDisputed: "disputed",
  preset: "preset",
};

const FILTER_KEYS: Array<keyof SearchFilters> = [
  "query",
  "osis",
  "collection",
  "author",
  "sourceType",
  "theologicalTradition",
  "topicDomain",
  "collectionFacets",
  "datasetFacets",
  "variantFacets",
  "dateStart",
  "dateEnd",
  "includeVariants",
  "includeDisputed",
  "preset",
];

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
    theologicalTradition: normalizeInput(params.get(KEY_MAP.theologicalTradition)),
    topicDomain: normalizeInput(params.get(KEY_MAP.topicDomain)),
    collectionFacets: normalizeList(params.get(KEY_MAP.collectionFacets)),
    datasetFacets: normalizeList(params.get(KEY_MAP.datasetFacets)),
    variantFacets: normalizeList(params.get(KEY_MAP.variantFacets)),
    dateStart: normalizeInput(params.get(KEY_MAP.dateStart)),
    dateEnd: normalizeInput(params.get(KEY_MAP.dateEnd)),
    includeVariants: parseBoolean(params.get(KEY_MAP.includeVariants)),
    includeDisputed: parseBoolean(params.get(KEY_MAP.includeDisputed)),
    preset: normalizeInput(params.get(KEY_MAP.preset)),
  };
}

export function serializeSearchParams(filters: Partial<SearchFilters>): string {
  const params = new URLSearchParams();
  FILTER_KEYS.forEach((key) => {
    const paramKey = KEY_MAP[key];
    const value = filters[key];
    if (typeof value === "string") {
      const trimmed = value.trim();
      if (trimmed) {
        params.set(paramKey, trimmed);
      }
      return;
    }

    if (Array.isArray(value)) {
      if (value.length > 0) {
        params.set(
          paramKey,
          value.map((item) => item.trim()).filter(Boolean).join(","),
        );
      }
      return;
    }

    if (typeof value === "boolean") {
      if (value) {
        params.set(paramKey, "1");
      }
    }
  });
  return params.toString();
}
