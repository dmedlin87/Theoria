import SearchPageClient from "./components/SearchPageClient";
import { getApiBaseUrl } from "../lib/api";
import { parseSearchParams, type SearchFilters } from "./searchParams";
import { type ErrorDetails, parseErrorResponse } from "../lib/errorUtils";
import type { components } from "../lib/generated/api";

type SearchResponse = components["schemas"]["HybridSearchResponse"];

type SearchPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

type InitialSearchData = {
  filters: SearchFilters;
  results: SearchResponse | null;
  error: ErrorDetails | null;
  rerankerName: string | null;
  hasSearched: boolean;
};

function buildQueryString(params: Record<string, string | string[] | undefined>): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.forEach((item) => {
        if (item != null) {
          query.append(key, item);
        }
      });
      return;
    }
    if (typeof value === "string") {
      query.set(key, value);
    }
  });
  return query.toString();
}

async function fetchInitialSearchData(
  params: Record<string, string | string[] | undefined>,
): Promise<InitialSearchData> {
  const queryString = buildQueryString(params);
  const filters = parseSearchParams(queryString);
  if (!queryString) {
    return {
      filters,
      results: null,
      error: null,
      rerankerName: null,
      hasSearched: false,
    };
  }

  const apiHeaders: Record<string, string> = { Accept: "application/json" };
  const apiKey = process.env.THEO_SEARCH_API_KEY?.trim();
  if (apiKey) {
    if (/^Bearer\s+/i.test(apiKey)) {
      apiHeaders.Authorization = apiKey;
    } else {
      apiHeaders["X-API-Key"] = apiKey;
    }
  }

  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const target = `${baseUrl}/search${queryString ? `?${queryString}` : ""}`;

  try {
    const response = await fetch(target, {
      headers: apiHeaders,
      next: { revalidate: 30 },
    });
    const rerankerHeader = response.headers.get("x-reranker");
    const rerankerName = rerankerHeader && rerankerHeader.trim() ? rerankerHeader.trim() : null;

    if (!response.ok) {
      const error = await parseErrorResponse(
        response,
        `Search failed with status ${response.status}`,
      );
      return {
        filters,
        results: null,
        error,
        rerankerName,
        hasSearched: true,
      };
    }

    const results = (await response.json()) as SearchResponse;
    return {
      filters,
      results,
      error: null,
      rerankerName,
      hasSearched: true,
    };
  } catch (error) {
    const message =
      error instanceof Error && error.message ? error.message : "Search request failed";
    return {
      filters,
      results: null,
      error: { message, traceId: null },
      rerankerName: null,
      hasSearched: true,
    };
  }
}

export default async function SearchPage({ searchParams }: SearchPageProps) {
  const resolvedSearchParams = await searchParams;
  const initialData = await fetchInitialSearchData(resolvedSearchParams);
  return (
    <SearchPageClient
      initialFilters={initialData.filters}
      initialResults={initialData.results}
      initialError={initialData.error}
      initialRerankerName={initialData.rerankerName}
      initialHasSearched={initialData.hasSearched}
    />
  );
}
