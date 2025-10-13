"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";

import ErrorCallout from "../../components/ErrorCallout";
import { useToast } from "../../components/Toast";
import UiModeToggle from "../../components/UiModeToggle";
import { buildPassageLink, formatAnchor } from "../../lib/api";
import { type ErrorDetails, parseErrorResponse } from "../../lib/errorUtils";
import type { components } from "../../lib/generated/api";
import { emitTelemetry, submitFeedback } from "../../lib/telemetry";
import type { FeedbackEventInput } from "../../lib/telemetry";
import { usePersistentSort } from "../../lib/usePersistentSort";
import { useUiModePreference } from "../../lib/useUiModePreference";
import { sortDocumentGroups, SortableDocumentGroup } from "../groupSorting";
import { SortControls } from "./SortControls";
import { SavedSearchControls } from "./SavedSearchControls";
import { DiffWorkspace } from "./DiffWorkspace";
import { SearchSkeleton } from "./SearchSkeleton";
import {
  parseSearchParams,
  serializeSearchParams,
  type SearchFilters,
} from "../searchParams";
import {
  COLLECTION_FACETS,
  CUSTOM_PRESET_VALUE,
  DATASET_FILTERS,
  DATASET_LABELS,
  DOMAIN_LABELS,
  DOMAIN_OPTIONS,
  getPresetLabel,
  MODE_PRESETS,
  SOURCE_LABELS,
  SOURCE_OPTIONS,
  TRADITION_LABELS,
  TRADITION_OPTIONS,
  VARIANT_FILTERS,
  VARIANT_LABELS,
} from "./filters/constants";
import { useSearchFiltersState } from "./filters/useSearchFiltersState";
import type {
  FilterDisplay,
  SavedSearch,
  SavedSearchFilterChip,
} from "./filters/types";

const SAVED_SEARCH_STORAGE_KEY = "theo.search.saved";
const FILTER_FIELD_KEYS: Array<keyof SearchFilters> = [
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
const VISUALLY_HIDDEN_STYLES: CSSProperties = {
  border: 0,
  clip: "rect(0 0 0 0)",
  height: "1px",
  margin: "-1px",
  overflow: "hidden",
  padding: 0,
  position: "absolute",
  width: "1px",
  whiteSpace: "nowrap",
};
const EMPTY_FILTERS: SearchFilters = {
  query: "",
  osis: "",
  collection: "",
  author: "",
  sourceType: "",
  theologicalTradition: "",
  topicDomain: "",
  collectionFacets: [],
  datasetFacets: [],
  variantFacets: [],
  dateStart: "",
  dateEnd: "",
  includeVariants: false,
  includeDisputed: false,
  preset: "",
};

function createEmptyFilters(): SearchFilters {
  return {
    ...EMPTY_FILTERS,
    collectionFacets: [],
    datasetFacets: [],
    variantFacets: [],
  };
}

function normalizeBoolean(value: unknown): boolean {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "number") {
    return value !== 0;
  }
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    return ["1", "true", "yes", "on"].includes(normalized);
  }
  return false;
}

function normalizeString(value: unknown): string {
  if (typeof value === "string") {
    return value.trim();
  }
  return "";
}

export function normalizeStringArray(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .filter((item): item is string => typeof item === "string")
      .map((item) => item.trim())
      .filter(Boolean);
  }
  if (typeof value === "string") {
    return value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return [];
}

function normalizeFiltersFromPartial(filters?: Partial<SearchFilters> | null): SearchFilters {
  const normalized = createEmptyFilters();
  if (!filters) {
    return normalized;
  }

  normalized.query = normalizeString(filters.query);
  normalized.osis = normalizeString(filters.osis);
  normalized.collection = normalizeString(filters.collection);
  normalized.author = normalizeString(filters.author);
  normalized.sourceType = normalizeString(filters.sourceType);
  normalized.theologicalTradition = normalizeString(filters.theologicalTradition);
  normalized.topicDomain = normalizeString(filters.topicDomain);
  normalized.collectionFacets = normalizeStringArray(filters.collectionFacets);
  normalized.datasetFacets = normalizeStringArray(filters.datasetFacets);
  normalized.variantFacets = normalizeStringArray(filters.variantFacets);
  normalized.dateStart = normalizeString(filters.dateStart);
  normalized.dateEnd = normalizeString(filters.dateEnd);
  normalized.includeVariants = normalizeBoolean(filters.includeVariants);
  normalized.includeDisputed = normalizeBoolean(filters.includeDisputed);
  normalized.preset = normalizeString(filters.preset);

  return normalized;
}

function extractFiltersFromLegacySavedSearch(
  raw: Partial<SavedSearch> & Record<string, unknown>,
): SearchFilters {
  const candidateFilters = raw.filters as unknown;
  if (typeof candidateFilters === "string") {
    return normalizeFiltersFromPartial(parseSearchParams(candidateFilters));
  }
  if (candidateFilters && typeof candidateFilters === "object") {
    return normalizeFiltersFromPartial(candidateFilters as Partial<SearchFilters>);
  }

  const queryString = raw.queryString;
  if (typeof queryString === "string" && queryString.trim()) {
    return normalizeFiltersFromPartial(parseSearchParams(queryString));
  }

  const inlineFilters: Partial<SearchFilters> = {};
  FILTER_FIELD_KEYS.forEach((key) => {
    const value = raw[key as keyof typeof raw];
    if (value !== undefined) {
      (inlineFilters as Record<string, unknown>)[key] = value as unknown;
    }
  });

  if (Object.keys(inlineFilters).length > 0) {
    return normalizeFiltersFromPartial(inlineFilters);
  }

  return createEmptyFilters();
}

function normalizeSavedSearchEntry(entry: unknown): SavedSearch | null {
  if (typeof entry === "string" && entry.trim()) {
    const timestamp = Date.now();
    return {
      id: `legacy-${timestamp}`,
      name: "Recovered search",
      filters: normalizeFiltersFromPartial(parseSearchParams(entry)),
      createdAt: timestamp,
    };
  }

  if (!entry || typeof entry !== "object") {
    return null;
  }

  const raw = entry as Partial<SavedSearch> & Record<string, unknown>;
  const filters = extractFiltersFromLegacySavedSearch(raw);
  const createdAtValue = raw.createdAt;
  const createdAt =
    typeof createdAtValue === "number" && Number.isFinite(createdAtValue)
      ? createdAtValue
      : Date.now();
  const rawId = raw.id;
  const id =
    typeof rawId === "string" && rawId.trim()
      ? rawId.trim()
      : `legacy-${createdAt}-${Math.random().toString(36).slice(2, 8)}`;
  const potentialName =
    typeof raw.name === "string" && raw.name.trim()
      ? raw.name.trim()
      : typeof raw.title === "string" && raw.title.trim()
        ? raw.title.trim()
        : "Recovered search";

  return {
    id,
    name: potentialName,
    filters,
    createdAt,
  };
}

function formatSavedSearchFilters(filters: SearchFilters): FilterDisplay {
  const chips: SavedSearchFilterChip[] = [];
  const pushChip = (text: string) => {
    if (text) {
      chips.push({ id: `${chips.length}-${text}`, text });
    }
  };

  if (filters.query) {
    pushChip(`Query: ${filters.query}`);
  }
  if (filters.osis) {
    pushChip(`Passage: ${filters.osis}`);
  }
  if (filters.collection) {
    pushChip(`Collection: ${filters.collection}`);
  }
  if (filters.author) {
    pushChip(`Author: ${filters.author}`);
  }
  if (filters.sourceType) {
    const label = SOURCE_LABELS.get(filters.sourceType) ?? filters.sourceType;
    pushChip(`Source: ${label}`);
  }
  if (filters.theologicalTradition) {
    const label =
      TRADITION_LABELS.get(filters.theologicalTradition) ?? filters.theologicalTradition;
    pushChip(`Tradition: ${label}`);
  }
  if (filters.topicDomain) {
    const label = DOMAIN_LABELS.get(filters.topicDomain) ?? filters.topicDomain;
    pushChip(`Topic: ${label}`);
  }
  if (filters.collectionFacets.length > 0) {
    pushChip(`Collection facets: ${filters.collectionFacets.join(", ")}`);
  }
  if (filters.datasetFacets.length > 0) {
    const labels = filters.datasetFacets.map(
      (value) => DATASET_LABELS.get(value) ?? value,
    );
    pushChip(`Datasets: ${labels.join(", ")}`);
  }
  if (filters.variantFacets.length > 0) {
    const labels = filters.variantFacets.map((value) => VARIANT_LABELS.get(value) ?? value);
    pushChip(`Variant facets: ${labels.join(", ")}`);
  }
  if (filters.dateStart || filters.dateEnd) {
    let range = "";
    if (filters.dateStart && filters.dateEnd) {
      range = `${filters.dateStart}–${filters.dateEnd}`;
    } else if (filters.dateStart) {
      range = `From ${filters.dateStart}`;
    } else if (filters.dateEnd) {
      range = `Until ${filters.dateEnd}`;
    }
    if (range) {
      pushChip(`Date: ${range}`);
    }
  }
  if (filters.includeVariants) {
    pushChip("Variants on");
  }
  if (filters.includeDisputed) {
    pushChip("Disputed readings on");
  }
  if (filters.preset) {
    pushChip(`Preset: ${getPresetLabel(filters.preset)}`);
  }

  const description = chips.map((chip) => chip.text).join("; ");

  return { chips, description };
}


type SearchResult = components["schemas"]["HybridSearchResult"];

type SearchResponse = components["schemas"]["HybridSearchResponse"];

export type DocumentGroup = SortableDocumentGroup & {
  documentId: string;
  passages: SearchResult[];
};

export type DiffSummary = {
  first: DocumentGroup;
  second: DocumentGroup;
  uniqueToFirst: string[];
  uniqueToSecond: string[];
  shared: number;
};

type SearchPageClientProps = {
  initialFilters: SearchFilters;
  initialResults: SearchResponse | null;
  initialError: ErrorDetails | null;
  initialRerankerName: string | null;
  initialHasSearched: boolean;
};

function buildDocumentGroupsFromResponse(
  payload: SearchResponse | null,
): DocumentGroup[] {
  if (!payload?.results?.length) {
    return [];
  }
  const grouped = new Map<string, DocumentGroup>();
  for (const result of payload.results) {
    let group = grouped.get(result.document_id);
    if (!group) {
      group = {
        documentId: result.document_id,
        title: result.document_title ?? "Untitled document",
        rank: result.document_rank ?? null,
        score: result.document_score ?? result.score ?? null,
        passages: [],
      } satisfies DocumentGroup;
      grouped.set(result.document_id, group);
    }
    if (group.rank == null && typeof result.document_rank === "number") {
      group.rank = result.document_rank;
    }
    const candidateScore = result.document_score ?? result.score ?? null;
    if (typeof candidateScore === "number") {
      if (typeof group.score !== "number" || candidateScore > group.score) {
        group.score = candidateScore;
      }
    }
    group.passages.push(result);
  }
  return Array.from(grouped.values());
}

function escapeRegExp(value: string): string {
  return value.replace(/[\^$.*+?()\[\]{}|]/g, "\\$&");
}

function highlightTokens(text: string, tokens: string[]): JSX.Element {
  if (!tokens.length) {
    return <>{text}</>;
  }
  const pattern = new RegExp(`(${tokens.map(escapeRegExp).join("|")})`, "gi");
  const parts = text.split(pattern);
  return (
    <>
      {parts.map((part, index) =>
        tokens.some((token) => token.toLowerCase() === part.toLowerCase()) ? (
          <mark key={`${part}-${index}`}>{part}</mark>
        ) : (
          <span key={`${part}-${index}`}>{part}</span>
        )
      )}
    </>
  );
}

export default function SearchPageClient({
  initialFilters,
  initialResults,
  initialError,
  initialRerankerName,
  initialHasSearched,
}: SearchPageClientProps): JSX.Element {
  const router = useRouter();
  const searchParams = useSearchParams();
  const searchParamsString = searchParams.toString();
  const skipNextHydratedSearchRef = useRef(initialHasSearched);
  const [uiMode, setUiMode] = useUiModePreference();
  const isAdvancedUi = uiMode === "advanced";
  const { addToast } = useToast();
  const {
    state: {
      query,
      osis,
      collection,
      author,
      sourceType,
      theologicalTradition,
      topicDomain,
      collectionFacets,
      datasetFacets,
      variantFacets,
      dateStart,
      dateEnd,
      includeVariants,
      includeDisputed,
      presetSelection,
    },
    setState: {
      setQuery,
      setOsis,
      setCollection,
      setAuthor,
      setSourceType,
      setTheologicalTradition,
      setTopicDomain,
      setCollectionFacets,
      setDatasetFacets,
      setVariantFacets,
      setDateStart,
      setDateEnd,
      setIncludeVariants,
      setIncludeDisputed,
      setPresetSelection,
    },
    derived: { presetIsCustom, currentFilters, filterChips, queryTokens },
    actions: {
      markPresetAsCustom,
      applyFilters,
      toggleCollectionFacet,
      toggleDatasetFacet,
      toggleVariantFacet,
    },
  } = useSearchFiltersState(initialFilters);
  const [isPresetChanging, setIsPresetChanging] = useState(false);
  const [sortKey, setSortKey] = usePersistentSort();
  const [groups, setGroups] = useState<DocumentGroup[]>(() =>
    sortDocumentGroups(buildDocumentGroupsFromResponse(initialResults), sortKey),
  );
  const [isSearching, setIsSearching] = useState(false);
  const [searchAbortController, setSearchAbortController] = useState<AbortController | null>(null);
  const [error, setError] = useState<ErrorDetails | null>(initialError);
  const [hasSearched, setHasSearched] = useState(initialHasSearched);
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>([]);
  const [savedSearchName, setSavedSearchName] = useState("");
  const [diffSelection, setDiffSelection] = useState<string[]>([]);
  const [activeActionsGroupId, setActiveActionsGroupId] = useState<string | null>(null);
  const [lastSearchFilters, setLastSearchFilters] = useState<SearchFilters | null>(
    initialHasSearched ? { ...initialFilters } : null,
  );
  const [rerankerName, setRerankerName] = useState<string | null>(initialRerankerName);
  const queryInputRef = useRef<HTMLInputElement | null>(null);
  const osisInputRef = useRef<HTMLInputElement | null>(null);
  const isBeginnerMode = uiMode === "simple";

  const arraysEqual = useCallback((left: string[], right: string[]) => {
    if (left === right) return true;
    if (left.length !== right.length) return false;
    return left.every((value, index) => value === right[index]);
  }, []);

  const updateUrlForFilters = useCallback(
    (filters: SearchFilters) => {
      const currentQuery = searchParams.toString();
      const nextQuery = serializeSearchParams(filters);
      if (currentQuery !== nextQuery) {
        skipNextHydratedSearchRef.current = true;
        router.replace(`/search${nextQuery ? `?${nextQuery}` : ""}`, { scroll: false });
      }
    },
    [router, searchParams],
  );

  const runSearch = useCallback(
    async (filters: SearchFilters) => {
      // Cancel any existing search
      if (searchAbortController) {
        searchAbortController.abort();
      }

      const abortController = new AbortController();
      setSearchAbortController(abortController);
      setIsSearching(true);
      setError(null);
      setHasSearched(true);
      setLastSearchFilters(filters);
      setRerankerName(null);

      const perf = typeof performance !== "undefined" ? performance : null;
      const requestStart = perf ? perf.now() : null;
      let retrievalEnd: number | null = null;
      let renderEnd: number | null = null;
      let success = false;

      try {
        const searchQuery = serializeSearchParams(filters);
        const response = await fetch(`/api/search${searchQuery ? `?${searchQuery}` : ""}`, {
          cache: "no-store",
          signal: abortController.signal,
        });
        const rerankerHeader = response.headers.get("x-reranker");
        setRerankerName(
          rerankerHeader && rerankerHeader.trim() ? rerankerHeader.trim() : null,
        );
        retrievalEnd = perf ? perf.now() : null;
        if (!response.ok) {
          const errorDetails = await parseErrorResponse(
            response,
            `Search failed with status ${response.status}`,
          );
          setGroups([]);
          setError(errorDetails);
          renderEnd = perf ? perf.now() : null;
        } else {
          const payload = (await response.json()) as SearchResponse;
          const nextGroups = sortDocumentGroups(
            buildDocumentGroupsFromResponse(payload),
            sortKey,
          );
          setGroups(nextGroups);
          renderEnd = perf ? perf.now() : null;
          success = true;
        }
      } catch (fetchError) {
        // Don't show error if the request was aborted
        if (fetchError instanceof Error && fetchError.name === "AbortError") {
          return;
        }

        if (retrievalEnd === null && perf) {
          retrievalEnd = perf.now();
        }
        renderEnd = perf ? perf.now() : null;
        const message =
          fetchError instanceof Error && fetchError.message
            ? fetchError.message
            : "Search failed";
        const traceId =
          typeof fetchError === "object" && fetchError && "traceId" in fetchError
            ? ((fetchError as { traceId?: string | null }).traceId ?? null)
            : null;
        setError({ message, traceId });
        setGroups([]);
      } finally {
        setIsSearching(false);
        setSearchAbortController(null);
        if (requestStart !== null) {
          const events: {
            event: string;
            durationMs: number;
            metadata?: Record<string, unknown>;
          }[] = [];
          if (retrievalEnd !== null) {
            events.push({
              event: "search.retrieval",
              durationMs: Math.max(0, retrievalEnd - requestStart),
              metadata: { success },
            });
          }
          if (renderEnd !== null) {
            const renderStart = retrievalEnd ?? requestStart;
            events.push({
              event: "search.results",
              durationMs: Math.max(0, renderEnd - renderStart),
              metadata: { success },
            });
          }
          if (events.length) {
            void emitTelemetry(events, { page: "search" });
          }
        }
      }
    },
    [sortKey, searchAbortController],
  );

  const handleSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const filters = currentFilters;

    updateUrlForFilters(filters);
    await runSearch(filters);
  };

  const handleShowErrorDetails = useCallback(
    (traceId: string | null) => {
      const detailMessage = traceId
        ? `Trace ID: ${traceId}`
        : "No additional trace information is available.";
      addToast({ type: "info", title: "Trace details", message: detailMessage });
    },
    [addToast],
  );

  const handleRetrySearch = useCallback(() => {
    if (lastSearchFilters && !isSearching) {
      void runSearch(lastSearchFilters);
    }
  }, [lastSearchFilters, runSearch, isSearching]);

  const handlePassageClick = useCallback(
    (result: SearchResult) => {
      const queryValue = (
        lastSearchFilters?.query ?? currentFilters.query ?? ""
      ).trim();
      const passageScore =
        typeof result.score === "number" ? result.score : undefined;
      const vectorScore =
        typeof result.vector_score === "number" ? result.vector_score : undefined;
      const lexicalScore =
        typeof result.lexical_score === "number" ? result.lexical_score : undefined;
      const documentScore =
        typeof result.document_score === "number" ? result.document_score : undefined;
      const rankingScore =
        passageScore ?? vectorScore ?? lexicalScore ?? undefined;
      const payload = {
        action: "click",
        documentId: result.document_id,
        passageId: result.id,
        ...(typeof result.rank === "number" ? { rank: result.rank } : {}),
        ...(typeof rankingScore === "number" ? { score: rankingScore } : {}),
        ...(typeof documentScore === "number" ? { confidence: documentScore } : {}),
        ...(queryValue ? { query: queryValue } : {}),
      } satisfies FeedbackEventInput;
      void submitFeedback(payload);
    },
    [currentFilters.query, lastSearchFilters],
  );

  const handlePresetChange = useCallback(
    (value: string) => {
      if (value === CUSTOM_PRESET_VALUE) {
        setPresetSelection(CUSTOM_PRESET_VALUE);
        setIsPresetChanging(false);
        return;
      }
      if (isSearching) {
        return; // Prevent preset change during active search
      }
      setIsPresetChanging(true);
      setPresetSelection(value);
      const presetConfig = MODE_PRESETS.find((candidate) => candidate.value === value);
      const nextFilters: SearchFilters = {
        ...currentFilters,
        ...(presetConfig?.filters ?? {}),
        collectionFacets: presetConfig?.filters?.collectionFacets
          ? [...presetConfig.filters.collectionFacets]
          : [...currentFilters.collectionFacets],
        datasetFacets: presetConfig?.filters?.datasetFacets
          ? [...presetConfig.filters.datasetFacets]
          : [...currentFilters.datasetFacets],
        variantFacets: presetConfig?.filters?.variantFacets
          ? [...presetConfig.filters.variantFacets]
          : [...currentFilters.variantFacets],
        preset: value,
      };
      applyFilters(nextFilters);
      updateUrlForFilters(nextFilters);
      void runSearch(nextFilters).finally(() => setIsPresetChanging(false));
    },
    [applyFilters, currentFilters, runSearch, updateUrlForFilters, isSearching],
  );

  const handleSavedSearchSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const trimmedName = savedSearchName.trim();
      if (!trimmedName) return;

      const filtersToPersist: SearchFilters = {
        ...currentFilters,
        collectionFacets: [...currentFilters.collectionFacets],
        datasetFacets: [...currentFilters.datasetFacets],
        variantFacets: [...currentFilters.variantFacets],
      };
      const nextSearch: SavedSearch = {
        id: crypto.randomUUID?.() ?? `${Date.now()}`,
        name: trimmedName,
        filters: filtersToPersist,
        createdAt: Date.now(),
      };
      let didUpdate = false;
      setSavedSearches((current) => {
        const existingIndex = current.findIndex((item) => item.name === trimmedName);
        if (existingIndex >= 0) {
          didUpdate = true;
          const updated = [...current];
          updated[existingIndex] = nextSearch;
          return updated;
        }
        return [...current, nextSearch].sort((a, b) => b.createdAt - a.createdAt);
      });
      setSavedSearchName("");
      addToast({
        type: "success",
        title: didUpdate ? "Saved search updated" : "Saved search created",
        message: didUpdate
          ? `Updated saved search “${trimmedName}”.`
          : `Saved search “${trimmedName}” is ready to reuse.`,
      });
    },
    [currentFilters, savedSearchName, addToast],
  );

  const handleApplySavedSearch = useCallback(
    async (saved: SavedSearch) => {
      if (!isSearching) {
        addToast({ type: "info", title: "Saved search applied", message: `Running “${saved.name}”.` });
        applyFilters(saved.filters);
        updateUrlForFilters(saved.filters);
        await runSearch(saved.filters);
      }
    },
    [addToast, applyFilters, runSearch, updateUrlForFilters, isSearching],
  );

  const handleDeleteSavedSearch = useCallback(
    (id: string) => {
      setSavedSearches((current) => {
        const target = current.find((saved) => saved.id === id);
        if (target) {
          addToast({ type: "info", title: "Saved search removed", message: `Deleted “${target.name}”.` });
        }
        return current.filter((saved) => saved.id !== id);
      });
    },
    [addToast],
  );

  const handleExportGroup = useCallback(
    (group: DocumentGroup) => {
      const filtersSnapshot: SearchFilters = {
        ...currentFilters,
        collectionFacets: [...currentFilters.collectionFacets],
        datasetFacets: [...currentFilters.datasetFacets],
        variantFacets: [...currentFilters.variantFacets],
      };
      const exportPayload = {
        exportedAt: new Date().toISOString(),
        queryString: serializeSearchParams(filtersSnapshot),
        filters: filtersSnapshot,
        dataset: {
          datasets: [...filtersSnapshot.datasetFacets],
          variants: [...filtersSnapshot.variantFacets],
        },
        group,
      };
      const blob = new Blob([JSON.stringify(exportPayload, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${group.title.replace(/[^a-z0-9]+/gi, "_") || "search"}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    },
    [currentFilters],
  );

  const handleToggleDiffGroup = useCallback((groupId: string) => {
    setDiffSelection((current) => {
      const exists = current.includes(groupId);
      if (exists) {
        return current.filter((id) => id !== groupId);
      }
      if (current.length >= 2) {
        const lastSelected = current[current.length - 1];
        return lastSelected ? [lastSelected, groupId] : [groupId];
      }
      return [...current, groupId];
    });
  }, []);

  const clearDiffSelection = useCallback(() => setDiffSelection([]), []);

  const diffSummary = useMemo<DiffSummary | null>(() => {
    if (diffSelection.length < 2) {
      return null;
    }
    const [firstId, secondId] = diffSelection;
    const first = groups.find((group) => group.documentId === firstId);
    const second = groups.find((group) => group.documentId === secondId);
    if (!first || !second) {
      return null;
    }
    const firstPassages = new Set(first.passages.map((passage) => passage.id));
    const secondPassages = new Set(second.passages.map((passage) => passage.id));

    const uniqueToFirst = first.passages
      .filter((passage) => !secondPassages.has(passage.id))
      .map((passage) => passage.id);
    const uniqueToSecond = second.passages
      .filter((passage) => !firstPassages.has(passage.id))
      .map((passage) => passage.id);

    return {
      first,
      second,
      uniqueToFirst,
      uniqueToSecond,
      shared:
        first.passages.length +
        second.passages.length -
        uniqueToFirst.length -
        uniqueToSecond.length,
    } satisfies DiffSummary;
  }, [diffSelection, groups]);

  const activePreset = useMemo(() => {
    const value = presetIsCustom ? CUSTOM_PRESET_VALUE : presetSelection;
    return MODE_PRESETS.find((candidate) => candidate.value === value);
  }, [presetIsCustom, presetSelection]);

  const advancedFilterControls = (
    <div className="search-advanced-controls">
      <div>
        <label className="search-form__label">
          <span className="search-form__label-text">Mode preset</span>
          <select
            name="preset"
            value={presetIsCustom ? CUSTOM_PRESET_VALUE : presetSelection}
            onChange={(event) => handlePresetChange(event.target.value)}
            className="search-form__select"
            disabled={isSearching || isPresetChanging}
            aria-busy={isPresetChanging}
          >
            {MODE_PRESETS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        {activePreset?.description && (
          <p className="search-advanced-help" style={{ marginTop: "0.35rem" }}>
            {activePreset.description}
          </p>
        )}
      </div>
      <label className="search-form__label">
        <span className="search-form__label-text">Collection</span>
        <input
          name="collection"
          type="text"
          value={collection}
          onChange={(event) => {
            setCollection(event.target.value);
            markPresetAsCustom();
          }}
          placeholder="Gospels"
          className="search-form__input"
        />
      </label>
      <label className="search-form__label">
        <span className="search-form__label-text">Author</span>
        <input
          name="author"
          type="text"
          value={author}
          onChange={(event) => {
            setAuthor(event.target.value);
            markPresetAsCustom();
          }}
          placeholder="Jane Doe"
          className="search-form__input"
        />
      </label>
      <label className="search-form__label">
        <span className="search-form__label-text">Source type</span>
        <select
          name="source_type"
          value={sourceType}
          onChange={(event) => {
            setSourceType(event.target.value);
            markPresetAsCustom();
          }}
          className="search-form__select"
        >
          {SOURCE_OPTIONS.map((option) => (
            <option key={option.value || "any"} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <label className="search-form__label">
        <span className="search-form__label-text">Theological tradition</span>
        <select
          name="theological_tradition"
          value={theologicalTradition}
          onChange={(event) => {
            setTheologicalTradition(event.target.value);
            markPresetAsCustom();
          }}
          className="search-form__select"
        >
          {TRADITION_OPTIONS.map((option) => (
            <option key={option.value || "any"} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <label className="search-form__label">
        <span className="search-form__label-text">Topic domain</span>
        <select
          name="topic_domain"
          value={topicDomain}
          onChange={(event) => {
            setTopicDomain(event.target.value);
            markPresetAsCustom();
          }}
          className="search-form__select"
        >
          {DOMAIN_OPTIONS.map((option) => (
            <option key={option.value || "any"} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <fieldset className="search-fieldset">
        <legend className="search-fieldset__legend">Collection facets</legend>
        <div className="search-fieldset__grid">
          {COLLECTION_FACETS.map((facet) => (
            <label key={facet} className="search-fieldset__checkbox-label">
              <input
                type="checkbox"
                checked={collectionFacets.includes(facet)}
                onChange={() => toggleCollectionFacet(facet)}
              />
              {facet}
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset className="search-fieldset">
        <legend className="search-fieldset__legend">Dataset facets</legend>
        <div className="search-fieldset__grid">
          {DATASET_FILTERS.map((dataset) => {
            const isActive = datasetFacets.includes(dataset.value);
            return (
              <label key={dataset.value} className="search-dataset-item">
                <span className="search-dataset-item__header">
                  <input
                    type="checkbox"
                    checked={isActive}
                    onChange={() => toggleDatasetFacet(dataset.value)}
                  />
                  <strong>{dataset.label}</strong>
                </span>
                <span className="search-dataset-item__desc">
                  {dataset.description}
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>
      <fieldset className="search-fieldset">
        <legend className="search-fieldset__legend">Variant focus</legend>
        <div className="search-fieldset__grid">
          {VARIANT_FILTERS.map((variant) => (
            <label key={variant.value} className="search-fieldset__checkbox-label">
              <input
                type="checkbox"
                checked={variantFacets.includes(variant.value)}
                onChange={() => toggleVariantFacet(variant.value)}
              />
              {variant.label}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="search-date-fields">
        <label className="search-form__label">
          <span className="search-form__label-text">Date from</span>
          <input
            type="date"
            name="date_start"
            value={dateStart}
            onChange={(event) => {
              setDateStart(event.target.value);
              markPresetAsCustom();
            }}
            className="search-form__input"
          />
        </label>
        <label className="search-form__label">
          <span className="search-form__label-text">Date to</span>
          <input
            type="date"
            name="date_end"
            value={dateEnd}
            onChange={(event) => {
              setDateEnd(event.target.value);
              markPresetAsCustom();
            }}
            className="search-form__input"
          />
        </label>
      </div>
      <div className="search-fieldset__grid">
        <label className="search-fieldset__checkbox-label">
          <input
            type="checkbox"
            name="variants"
            checked={includeVariants}
            onChange={(event) => {
              setIncludeVariants(event.target.checked);
              markPresetAsCustom();
            }}
          />
          Include textual variants
        </label>
        <label className="search-fieldset__checkbox-label">
          <input
            type="checkbox"
            name="disputed"
            checked={includeDisputed}
            onChange={(event) => {
              setIncludeDisputed(event.target.checked);
              markPresetAsCustom();
            }}
          />
          Include disputed readings
        </label>
      </div>
    </div>
  );

  const handleGuidedPassageChip = (): void => {
    osisInputRef.current?.focus();
    setOsis((current) => (current ? current : "John.1.1-5"));
  };

  const handleGuidedTopicChip = (): void => {
    queryInputRef.current?.focus();
    setQuery((current) => (current ? current : "atonement theology"));
  };

  useEffect(() => {
    try {
      const stored = localStorage.getItem(SAVED_SEARCH_STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as unknown;
        if (Array.isArray(parsed)) {
          const normalized = parsed
            .map((entry) => normalizeSavedSearchEntry(entry))
            .filter((entry): entry is SavedSearch => entry !== null)
            .sort((a, b) => b.createdAt - a.createdAt);
          setSavedSearches(normalized);
        } else {
          const normalized = normalizeSavedSearchEntry(parsed);
          if (normalized) {
            setSavedSearches([normalized]);
          }
        }
      }
    } catch (storageError) {
      console.error("Failed to load saved searches", storageError);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(SAVED_SEARCH_STORAGE_KEY, JSON.stringify(savedSearches));
  }, [savedSearches]);

  useEffect(() => {
    const filters = parseSearchParams(searchParamsString);
    setQuery((current) => (current === filters.query ? current : filters.query));
    setOsis((current) => (current === filters.osis ? current : filters.osis));
    setCollection((current) => (current === filters.collection ? current : filters.collection));
    setAuthor((current) => (current === filters.author ? current : filters.author));
    setSourceType((current) => (current === filters.sourceType ? current : filters.sourceType));
    setTheologicalTradition((current) =>
      current === filters.theologicalTradition ? current : filters.theologicalTradition,
    );
    setTopicDomain((current) => (current === filters.topicDomain ? current : filters.topicDomain));
    setCollectionFacets((current) =>
      arraysEqual(current, filters.collectionFacets) ? current : filters.collectionFacets,
    );
    setDatasetFacets((current) =>
      arraysEqual(current, filters.datasetFacets) ? current : filters.datasetFacets,
    );
    setVariantFacets((current) =>
      arraysEqual(current, filters.variantFacets) ? current : filters.variantFacets,
    );
    setDateStart((current) => (current === filters.dateStart ? current : filters.dateStart));
    setDateEnd((current) => (current === filters.dateEnd ? current : filters.dateEnd));
    setIncludeVariants((current) =>
      current === filters.includeVariants ? current : filters.includeVariants,
    );
    setIncludeDisputed((current) =>
      current === filters.includeDisputed ? current : filters.includeDisputed,
    );
    setPresetSelection((current) => {
      const nextValue = filters.preset ? filters.preset : CUSTOM_PRESET_VALUE;
      return current === nextValue ? current : nextValue;
    });

    if (skipNextHydratedSearchRef.current) {
      skipNextHydratedSearchRef.current = false;
      return;
    }

    const hasFilters =
      Boolean(
        filters.query ||
          filters.osis ||
          filters.collection ||
          filters.author ||
          filters.sourceType ||
          filters.theologicalTradition ||
          filters.topicDomain ||
          filters.dateStart ||
          filters.dateEnd ||
          filters.preset,
      ) ||
      filters.collectionFacets.length > 0 ||
      filters.datasetFacets.length > 0 ||
      filters.variantFacets.length > 0 ||
      filters.includeVariants ||
      filters.includeDisputed;
    if (!hasFilters) {
      setHasSearched(false);
      setGroups([]);
      setError(null);
      setIsSearching(false);
      return;
    }

    void runSearch(filters);
  }, [arraysEqual, runSearch, searchParamsString]);

  useEffect(() => {
    setGroups((currentGroups) => sortDocumentGroups(currentGroups, sortKey));
  }, [sortKey]);

  useEffect(() => {
    setDiffSelection((current) =>
      current.filter((id) => groups.some((group) => group.documentId === id)),
    );
  }, [groups]);

  const savedSearchContent = (
    <SavedSearchControls
      savedSearchName={savedSearchName}
      onSavedSearchNameChange={setSavedSearchName}
      onSubmit={handleSavedSearchSubmit}
      savedSearches={savedSearches}
      onApplySavedSearch={handleApplySavedSearch}
      onDeleteSavedSearch={handleDeleteSavedSearch}
      formatFilters={formatSavedSearchFilters}
    />
  );

  return (
    <section className="search-page">
      {/* Accessibility: Announce search status */}
      <div role="status" aria-live="polite" aria-atomic="true" className="visually-hidden">
        {isSearching ? "Searching corpus..." : hasSearched && !error && groups.length === 0 ? "No results found" : hasSearched && groups.length > 0 ? `Found ${groups.length} document${groups.length === 1 ? "" : "s"}` : ""}
      </div>
      <h2>Search</h2>
      <p>Hybrid search with lexical, vector, and OSIS-aware filtering.</p>
      <div className="search-ui-mode-wrapper">
        <UiModeToggle mode={uiMode} onChange={setUiMode} />
      </div>

      <form
        onSubmit={handleSearch}
        aria-label="Search corpus"
        className="search-form"
      >
        <div className="search-form__fields">
          <div
            aria-label="Guided search suggestions"
            className="search-guided-chips"
          >
            <button
              type="button"
              onClick={handleGuidedPassageChip}
              className="search-guided-chip"
            >
              Search by passage
            </button>
            <button
              type="button"
              onClick={handleGuidedTopicChip}
              className="search-guided-chip"
            >
              Search by topic
            </button>
          </div>
          <label className="search-form__label">
            <span className="search-form__label-text">Query</span>
            <input
              name="q"
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search corpus"
              className="search-form__input"
              ref={queryInputRef}
            />
          </label>
          <label className="search-form__label">
            <span className="search-form__label-text">OSIS reference</span>
            <input
              name="osis"
              type="text"
              value={osis}
              onChange={(event) => setOsis(event.target.value)}
              placeholder="John.1.1-5"
              className="search-form__input"
              ref={osisInputRef}
            />
          </label>
        </div>

        {isBeginnerMode && (
          <p className="search-simple-mode-hint">
            Simple mode shows only the essentials. Use the advanced panel when you need presets, saved searches, or guardrail filters.
          </p>
        )}

        {isAdvancedUi ? (
          <div className="search-advanced-controls">{advancedFilterControls}</div>
        ) : (
          <details className="search-advanced-details">
            <summary className="search-advanced-summary">Advanced</summary>
            <p className="search-advanced-help">
              Expand to tune presets, guardrail filters, and dataset facets. Saved search tools live here too.
            </p>
            {advancedFilterControls}
          </details>
        )}

        <button 
          type="submit" 
          className={isSearching ? "search-form__button is-loading" : "search-form__button"}
          disabled={isSearching}
          aria-label={isSearching ? "Searching corpus..." : "Search corpus"}
        >
          {isSearching && <span className="button-loading-spinner" aria-hidden="true" />}
          {isSearching ? "Searching..." : "Search"}
        </button>
      </form>

      {isAdvancedUi ? (
        <section aria-label="Saved searches" className="search-saved-section">
          <h3>Saved searches</h3>
          {savedSearchContent}
        </section>
      ) : (
        <details className="search-advanced-details" style={{ margin: "2rem 0" }}>
          <summary className="search-advanced-summary">Saved searches</summary>
          <p className="search-advanced-help">
            Expand to store or recall presets. Saved searches remember every active filter.
          </p>
          {savedSearchContent}
        </details>
      )}

      <div style={{ margin: "1.5rem 0" }}>
        <SortControls value={sortKey} onChange={setSortKey} />
      </div>

      {rerankerName && (
        <span className="search-reranker-badge">
          Reranked by {rerankerName}
        </span>
      )}

      {filterChips.length > 0 && (
        <div className="search-filter-chips">
          {filterChips.map((chip) => (
            <span key={`${chip.label}-${chip.value}`} className="search-filter-chip">
              <strong>{chip.label}:</strong> {chip.value}
            </span>
          ))}
        </div>
      )}

      {diffSelection.length > 0 && (
        <DiffWorkspace
          diffSelection={diffSelection}
          diffSummary={diffSummary}
          onClear={clearDiffSelection}
        />
      )}

      {isSearching && (
        <>
          <p role="status" className="search-status">Searching...</p>
          <SearchSkeleton count={3} />
        </>
      )}
      {error && (
        <div style={{ marginTop: "1rem" }}>
          <ErrorCallout
            message={error.message}
            traceId={error.traceId}
            onRetry={handleRetrySearch}
            onShowDetails={handleShowErrorDetails}
            detailsLabel="Show details"
          />
        </div>
      )}
      {!isSearching && hasSearched && !error && groups.length === 0 && (
        <p className="search-no-results">No results found for the current query.</p>
      )}

      <div className="search-results">
        {groups.map((group) => {
          const isSelectedForDiff = diffSelection.includes(group.documentId);
          const diffLabel = isSelectedForDiff
            ? "Remove from diff"
            : diffSelection.length >= 2
            ? "Replace in diff"
            : "Add to diff";
          const showGroupActions = isAdvancedUi || activeActionsGroupId === group.documentId;
          return (
            <article
              key={group.documentId}
              className={`search-result-group${isSelectedForDiff ? " search-result-group--selected" : ""}`}
              tabIndex={0}
              onFocus={() => setActiveActionsGroupId(group.documentId)}
              onBlur={() =>
                setActiveActionsGroupId((current) =>
                  current === group.documentId ? null : current,
                )
              }
              onMouseEnter={() => setActiveActionsGroupId(group.documentId)}
              onMouseLeave={() =>
                setActiveActionsGroupId((current) =>
                  current === group.documentId ? null : current,
                )
              }
            >
              <header className="search-result-header">
                <div>
                  <h3 className="search-result-title">{group.title}</h3>
                  {typeof group.rank === "number" && (
                    <p className="search-result-meta">
                      Document rank #{group.rank}
                      {isAdvancedUi && (
                        <span
                          className="search-result-meta__hint"
                          title="Lower rank numbers indicate higher retrieval relevance."
                        >
                          (lower is better)
                        </span>
                      )}
                    </p>
                  )}
                  {typeof group.score === "number" && (
                    <p className="search-result-meta">
                      Document score {group.score.toFixed(2)}
                      {isAdvancedUi && (
                        <span
                          className="search-result-meta__hint"
                          title="Combined retriever confidence; higher scores indicate stronger matches."
                        >
                          (higher is better)
                        </span>
                      )}
                    </p>
                  )}
                </div>
                <div className="search-result-actions">
                  <button type="button" className="search-result-action-btn" onClick={() => handleExportGroup(group)}>
                    Export JSON
                  </button>
                  <button type="button" className="search-result-action-btn" onClick={() => handleToggleDiffGroup(group.documentId)}>
                    {diffLabel}
                  </button>
                </div>
              </header>
              <ul className="search-passages">
                {group.passages.map((result) => {
                  const anchorDescription = formatAnchor({
                    page_no: result.page_no ?? null,
                    t_start: result.t_start ?? null,
                    t_end: result.t_end ?? null,
                  });
                  return (
                    <li key={result.id} className="search-passage">
                      <div>
                        <div className="search-passage__content">
                          <p className="search-passage__text">{result.snippet}</p>
                          <Link
                            href={buildPassageLink(result.document_id, result.id, {
                              pageNo: result.page_no ?? null,
                              tStart: result.t_start ?? null,
                            })}
                            onClick={() => handlePassageClick(result)}
                            className="search-passage__link"
                          >
                            Open passage
                          </Link>
                        </div>
                        {(anchorDescription || result.osis_ref) && (
                          <div className="search-passage__details">
                            {anchorDescription && <p>{anchorDescription}</p>}
                            {result.osis_ref && <p>OSIS: {result.osis_ref}</p>}
                          </div>
                        )}
                        {Array.isArray(result.highlights) && result.highlights.length > 0 && (
                          <div className="search-passage__highlights">
                            {result.highlights.map((highlight) => (
                              <p key={highlight} className="search-passage__highlight">
                                {highlightTokens(highlight, queryTokens)}
                              </p>
                            ))}
                          </div>
                        )}
                        {typeof result.score === "number" && (
                          <p className="search-result-meta">
                            Passage score {result.score.toFixed(2)}
                            {isAdvancedUi && (
                              <span
                                className="search-result-meta__hint"
                                title="Reranker confidence for this passage; higher scores indicate stronger matches."
                              >
                                (higher is better)
                              </span>
                            )}
                          </p>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </article>
          );
        })}
      </div>
    </section>
  );
}
