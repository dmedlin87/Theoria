import { useRouter } from "next/navigation";
import { useCallback } from "react";

import type { components } from "./generated/api";
import { serializeSearchParams, type SearchFilters } from "../search/searchParams";

export type HybridSearchFilters = components["schemas"]["HybridSearchFilters"];

export type GuardrailSuggestion =
  | {
      action: "search";
      label: string;
      description?: string | null;
      query?: string | null;
      osis?: string | null;
      filters?: HybridSearchFilters | null;
    }
  | {
      action: "upload";
      label: string;
      description?: string | null;
      collection?: string | null;
    };

export type GuardrailFailureMetadata = {
  code: string;
  guardrail: "retrieval" | "generation" | "safety" | "ingest" | "unknown";
  suggestedAction: "search" | "upload" | "retry" | "none";
  filters?: HybridSearchFilters | null;
  safeRefusal: boolean;
  reason?: string | null;
};

type SearchSuggestion = Extract<GuardrailSuggestion, { action: "search" }>;

export function buildSearchUrl(suggestion: SearchSuggestion): string {
  const params: Partial<SearchFilters> = {};
  if (suggestion.query) {
    params.query = suggestion.query;
  }
  if (suggestion.osis) {
    params.osis = suggestion.osis;
  }
  const filters = suggestion.filters;
  if (filters) {
    if (typeof filters.collection === "string" && filters.collection) {
      params.collection = filters.collection;
    }
    if (typeof filters.author === "string" && filters.author) {
      params.author = filters.author;
    }
    if (typeof filters.source_type === "string" && filters.source_type) {
      params.sourceType = filters.source_type;
    }
    if (
      typeof filters.theological_tradition === "string" &&
      filters.theological_tradition
    ) {
      params.theologicalTradition = filters.theological_tradition;
    }
    if (typeof filters.topic_domain === "string" && filters.topic_domain) {
      params.topicDomain = filters.topic_domain;
    }
  }

  const queryString = serializeSearchParams(params);
  return `/search${queryString ? `?${queryString}` : ""}`;
}

type GuardrailActionOptions = {
  onSearchNavigate?: (url: string) => void;
  onUploadNavigate?: () => void;
};

export function useGuardrailActions(options?: GuardrailActionOptions) {
  const router = useRouter();
  const { onSearchNavigate, onUploadNavigate } = options ?? {};

  return useCallback(
    (suggestion: GuardrailSuggestion) => {
      if (suggestion.action === "search") {
        const url = buildSearchUrl(suggestion);
        if (onSearchNavigate) {
          onSearchNavigate(url);
        } else {
          router.push(url);
        }
        return;
      }

      if (suggestion.action === "upload") {
        if (onUploadNavigate) {
          onUploadNavigate();
        } else {
          router.push("/upload");
        }
      }
    },
    [onSearchNavigate, onUploadNavigate, router],
  );
}

