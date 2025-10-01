import SearchPageClient from "./components/SearchPageClient";
import { parseErrorResponse, type ErrorDetails } from "../lib/errorUtils";
import { getApiBaseUrl } from "../lib/api";
import { parseSearchParams, serializeSearchParams, type SearchFilters } from "./searchParams";
import type { SearchResponse } from "./types";

function toUrlSearchParams(
  params?: Record<string, string | string[] | undefined>,
): URLSearchParams {
  const searchParams = new URLSearchParams();
  if (!params) {
    return searchParams;
  }

  for (const [key, value] of Object.entries(params)) {
    if (Array.isArray(value)) {
      value.filter((entry) => entry != null).forEach((entry) => {
        searchParams.append(key, String(entry));
      });
    } else if (value != null) {
      searchParams.set(key, String(value));
    }
  }

  return searchParams;
}

function hasActiveFilters(filters: SearchFilters): boolean {
  if (
    filters.query ||
    filters.osis ||
    filters.collection ||
    filters.author ||
    filters.sourceType ||
    filters.theologicalTradition ||
    filters.topicDomain ||
    filters.dateStart ||
    filters.dateEnd ||
    filters.preset
  ) {
    return true;
  }

  if (
    filters.collectionFacets.length > 0 ||
    filters.datasetFacets.length > 0 ||
    filters.variantFacets.length > 0 ||
    filters.includeVariants ||
    filters.includeDisputed
  ) {
    return true;
  }

  return false;
}

async function fetchInitialSearch(
  filters: SearchFilters,
): Promise<{ response: SearchResponse | null; error: ErrorDetails | null; reranker: string | null }>
{
  if (!hasActiveFilters(filters)) {
    return { response: null, error: null, reranker: null };
  }

  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const query = serializeSearchParams(filters);
  const target = new URL("/search", baseUrl);
  if (query) {
    const params = new URLSearchParams(query);
    params.forEach((value, key) => {
      if (value) {
        target.searchParams.append(key, value);
      }
    });
  }

  const requestHeaders: Record<string, string> = { Accept: "application/json" };
  const apiKey = process.env.THEO_SEARCH_API_KEY?.trim();
  if (apiKey) {
    if (/^Bearer\s+/i.test(apiKey)) {
      requestHeaders.Authorization = apiKey;
    } else {
      requestHeaders["X-API-Key"] = apiKey;
    }
  }

  try {
    const response = await fetch(target, {
      headers: requestHeaders,
      next: { revalidate: 30 },
    });

    if (!response.ok) {
      const errorDetails = await parseErrorResponse(
        response,
        `Search failed with status ${response.status}`,
      );
      return { response: null, error: errorDetails, reranker: null };
    }

    const rerankerHeader = response.headers.get("x-reranker");
    const payload = (await response.json()) as SearchResponse;

    return {
      response: payload,
      error: null,
      reranker: rerankerHeader && rerankerHeader.trim() ? rerankerHeader.trim() : null,
    };
  } catch (error) {
    const message = error instanceof Error && error.message ? error.message : "Search failed";
    const traceId =
      typeof error === "object" && error && "traceId" in error
        ? ((error as { traceId?: string | null }).traceId ?? null)
        : null;
    return {
      response: null,
      error: { message, traceId },
      reranker: null,
    };
  }
}

export type SearchPageProps = {
  searchParams?: Record<string, string | string[] | undefined>;
};

export default async function SearchPage({ searchParams }: SearchPageProps): Promise<JSX.Element> {
  const initialSearchParams = toUrlSearchParams(searchParams);
  const filters = parseSearchParams(initialSearchParams);
  const { response, error, reranker } = await fetchInitialSearch(filters);

  return (
    <SearchPageClient
      initialFilters={filters}
      initialResponse={response}
      initialError={error}
      initialReranker={reranker}
      hasInitialSearch={hasActiveFilters(filters)}
    />
  );
}
