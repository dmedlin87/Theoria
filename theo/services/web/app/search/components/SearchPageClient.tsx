"use client";

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
import UiModeToggle from "../../components/UiModeToggle";
import { buildPassageLink, formatAnchor } from "../../lib/api";
import { parseErrorResponse, type ErrorDetails } from "../../lib/errorUtils";
import { emitTelemetry, submitFeedback } from "../../lib/telemetry";
import type { FeedbackEventInput } from "../../lib/telemetry";
import { usePersistentSort } from "../../lib/usePersistentSort";
import { useUiModePreference } from "../../lib/useUiModePreference";
import { SortControls } from "../SortControls";
import { sortDocumentGroups } from "../groupSorting";
import {
  parseSearchParams,
  serializeSearchParams,
  type SearchFilters,
} from "../searchParams";
import type { DocumentGroup, SavedSearch, SearchResponse, SearchResult } from "../types";
import DiffWorkspace from "./DiffWorkspace";
import SavedSearchesPanel from "./SavedSearchesPanel";
import SearchFiltersForm from "./SearchFiltersForm";
import SearchResultsList from "./SearchResultsList";

const SOURCE_OPTIONS = [
  { label: "Any source", value: "" },
  { label: "PDF", value: "pdf" },
  { label: "Markdown", value: "markdown" },
  { label: "YouTube", value: "youtube" },
  { label: "Transcript", value: "transcript" },
] as const;

const TRADITION_OPTIONS = [
  { label: "Any tradition", value: "" },
  { label: "Anglican Communion", value: "anglican" },
  { label: "Baptist", value: "baptist" },
  { label: "Roman Catholic", value: "catholic" },
  { label: "Eastern Orthodox", value: "orthodox" },
  { label: "Reformed", value: "reformed" },
  { label: "Wesleyan/Methodist", value: "wesleyan" },
] as const;

const DOMAIN_OPTIONS = [
  { label: "Any topic", value: "" },
  { label: "Christology", value: "christology" },
  { label: "Soteriology", value: "soteriology" },
  { label: "Ecclesiology", value: "ecclesiology" },
  { label: "Sacramental Theology", value: "sacramental" },
  { label: "Biblical Theology", value: "biblical-theology" },
  { label: "Christian Ethics", value: "ethics" },
] as const;

const COLLECTION_FACETS = [
  "Dead Sea Scrolls",
  "Nag Hammadi",
  "Church Fathers",
  "Second Temple",
] as const;

const DATASET_FILTERS = [
  {
    label: "Dead Sea Scrolls",
    value: "dss",
    description: "Qumran fragments and related parallels",
  },
  {
    label: "Nag Hammadi Codices",
    value: "nag-hammadi",
    description: "Gnostic corpus for comparative study",
  },
] as const;

const VARIANT_FILTERS = [
  { label: "Disputed readings", value: "disputed" },
  { label: "Harmonized expansions", value: "harmonized" },
  { label: "Orthographic shifts", value: "orthographic" },
] as const;

const DATASET_LABELS: Map<string, string> = new Map(
  DATASET_FILTERS.map((option) => [option.value, option.label] as const),
);
const VARIANT_LABELS: Map<string, string> = new Map(
  VARIANT_FILTERS.map((option) => [option.value, option.label] as const),
);
const SOURCE_LABELS: Map<string, string> = new Map(
  SOURCE_OPTIONS.map((option) => [option.value, option.label] as const),
);
const TRADITION_LABELS: Map<string, string> = new Map(
  TRADITION_OPTIONS.map((option) => [option.value, option.label] as const),
);
const DOMAIN_LABELS: Map<string, string> = new Map(
  DOMAIN_OPTIONS.map((option) => [option.value, option.label] as const),
);

const CUSTOM_PRESET_VALUE = "custom";
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

const SAVED_SEARCH_CHIP_CONTAINER_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "0.35rem",
  marginTop: "0.35rem",
};

const SAVED_SEARCH_CHIP_STYLE: CSSProperties = {
  background: "#e2e8f0",
  borderRadius: "999px",
  color: "#1e293b",
  display: "inline-flex",
  fontSize: "0.75rem",
  fontWeight: 500,
  lineHeight: 1.2,
  padding: "0.2rem 0.55rem",
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

type SavedSearchFilterChip = {
  id: string;
  text: string;
};

type FilterDisplay = {
  chips: SavedSearchFilterChip[];
  description: string;
};

type ModePreset = {
  value: string;
  label: string;
  description: string;
  filters?: Partial<SearchFilters>;
};

const MODE_PRESETS: ModePreset[] = [
  {
    value: CUSTOM_PRESET_VALUE,
    label: "Manual configuration",
    description: "Start with an empty slate and tune filters yourself.",
  },
  {
    value: "scholar",
    label: "Scholarly exegesis",
    description: "Variants + disputed passages with manuscript-heavy sources.",
    filters: {
      includeVariants: true,
      includeDisputed: true,
      collectionFacets: ["Dead Sea Scrolls", "Church Fathers"],
      datasetFacets: ["dss"],
      variantFacets: ["disputed"],
      sourceType: "pdf",
    },
  },
  {
    value: "devotional",
    label: "Devotional overview",
    description: "Focus on canonical material and mainstream commentary.",
    filters: {
      includeVariants: false,
      includeDisputed: false,
      collectionFacets: ["Church Fathers"],
      datasetFacets: [],
      variantFacets: [],
      sourceType: "markdown",
    },
  },
  {
    value: "textual-critical",
    label: "Textual criticism",
    description: "Surface disputed readings and variant apparatus notes.",
    filters: {
      includeVariants: true,
      includeDisputed: true,
      collectionFacets: ["Dead Sea Scrolls", "Second Temple"],
      datasetFacets: ["dss"],
      variantFacets: ["disputed", "harmonized"],
      sourceType: "pdf",
    },
  },
];

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

function normalizeStringArray(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .map((item) => (typeof item === "string" ? item.trim() : String(item ?? "")))
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
    } satisfies SavedSearch;
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
  } satisfies SavedSearch;
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

function getPresetLabel(value: string): string {
  const preset = MODE_PRESETS.find((item) => item.value === value);
  return preset ? preset.label : value;
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
        ),
      )}
    </>
  );
}

type DiffSummary = {
  first: DocumentGroup;
  second: DocumentGroup;
  uniqueToFirst: string[];
  uniqueToSecond: string[];
  shared: number;
};

function groupResults(response: SearchResponse | null): DocumentGroup[] {
  if (!response?.results) {
    return [];
  }
  const grouped = new Map<string, DocumentGroup>();
  response.results.forEach((result) => {
    const existing = grouped.get(result.document_id);
    if (!existing) {
      grouped.set(result.document_id, {
        documentId: result.document_id,
        title: result.document_title ?? "Untitled document",
        rank: result.document_rank ?? null,
        score: result.document_score ?? result.score ?? null,
        passages: [result],
      });
      return;
    }

    if (existing.rank == null && typeof result.document_rank === "number") {
      existing.rank = result.document_rank;
    }

    const candidateScore = result.document_score ?? result.score ?? null;
    if (typeof candidateScore === "number") {
      if (typeof existing.score !== "number" || candidateScore > existing.score) {
        existing.score = candidateScore;
      }
    }
    existing.passages.push(result);
  });

  return Array.from(grouped.values());
}

export type SearchPageClientProps = {
  initialFilters: SearchFilters;
  initialResponse: SearchResponse | null;
  initialError: ErrorDetails | null;
  initialReranker: string | null;
  hasInitialSearch: boolean;
};

export default function SearchPageClient({
  initialFilters,
  initialResponse,
  initialError,
  initialReranker,
  hasInitialSearch,
}: SearchPageClientProps): JSX.Element {
  const router = useRouter();
  const searchParams = useSearchParams();
  const skipNextHydratedSearchRef = useRef(hasInitialSearch);
  const [uiMode, setUiMode] = useUiModePreference();
  const isAdvancedUi = uiMode === "advanced";
  const [query, setQuery] = useState(initialFilters.query);
  const [osis, setOsis] = useState(initialFilters.osis);
  const [collection, setCollection] = useState(initialFilters.collection);
  const [author, setAuthor] = useState(initialFilters.author);
  const [sourceType, setSourceType] = useState(initialFilters.sourceType);
  const [theologicalTradition, setTheologicalTradition] = useState(
    initialFilters.theologicalTradition,
  );
  const [topicDomain, setTopicDomain] = useState(initialFilters.topicDomain);
  const [collectionFacets, setCollectionFacets] = useState<string[]>([
    ...initialFilters.collectionFacets,
  ]);
  const [datasetFacets, setDatasetFacets] = useState<string[]>([
    ...initialFilters.datasetFacets,
  ]);
  const [variantFacets, setVariantFacets] = useState<string[]>([
    ...initialFilters.variantFacets,
  ]);
  const [dateStart, setDateStart] = useState(initialFilters.dateStart);
  const [dateEnd, setDateEnd] = useState(initialFilters.dateEnd);
  const [includeVariants, setIncludeVariants] = useState(initialFilters.includeVariants);
  const [includeDisputed, setIncludeDisputed] = useState(initialFilters.includeDisputed);
  const [presetSelection, setPresetSelection] = useState<string>(
    initialFilters.preset || CUSTOM_PRESET_VALUE,
  );
  const [groups, setGroups] = useState<DocumentGroup[]>(() =>
    sortDocumentGroups(groupResults(initialResponse), undefined),
  );
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<ErrorDetails | null>(initialError);
  const [hasSearched, setHasSearched] = useState(hasInitialSearch && !!initialResponse);
  const [sortKey, setSortKey] = usePersistentSort();
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>([]);
  const [savedSearchName, setSavedSearchName] = useState("");
  const [diffSelection, setDiffSelection] = useState<string[]>([]);
  const [activeActionsGroupId, setActiveActionsGroupId] = useState<string | null>(null);
  const [lastSearchFilters, setLastSearchFilters] = useState<SearchFilters | null>(
    hasInitialSearch ? initialFilters : null,
  );
  const [rerankerName, setRerankerName] = useState<string | null>(initialReranker);
  const queryInputRef = useRef<HTMLInputElement | null>(null);
  const osisInputRef = useRef<HTMLInputElement | null>(null);
  const isBeginnerMode = uiMode === "simple";

  const presetIsCustom = presetSelection === CUSTOM_PRESET_VALUE || presetSelection === "";

  const markPresetAsCustom = useCallback(() => {
    setPresetSelection((current) =>
      current === CUSTOM_PRESET_VALUE ? current : CUSTOM_PRESET_VALUE,
    );
  }, []);

  const currentFilters = useMemo<SearchFilters>(
    () => ({
      query: query.trim(),
      osis: osis.trim(),
      collection: collection.trim(),
      author: author.trim(),
      sourceType,
      theologicalTradition: theologicalTradition.trim(),
      topicDomain: topicDomain.trim(),
      collectionFacets,
      datasetFacets,
      variantFacets,
      dateStart: dateStart.trim(),
      dateEnd: dateEnd.trim(),
      includeVariants,
      includeDisputed,
      preset: presetIsCustom ? "" : presetSelection.trim(),
    }),
    [
      author,
      collection,
      collectionFacets,
      datasetFacets,
      variantFacets,
      dateEnd,
      dateStart,
      theologicalTradition,
      topicDomain,
      includeDisputed,
      includeVariants,
      osis,
      presetIsCustom,
      presetSelection,
      query,
      sourceType,
    ],
  );

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

  const filterChips = useMemo(() => {
    const chips: { label: string; value: string }[] = [];
    if (collection) chips.push({ label: "Collection", value: collection });
    if (author) chips.push({ label: "Author", value: author });
    if (sourceType) chips.push({ label: "Source", value: sourceType });
    if (theologicalTradition)
      chips.push({ label: "Tradition", value: theologicalTradition });
    if (topicDomain) chips.push({ label: "Topic", value: topicDomain });
    collectionFacets.forEach((facet) => chips.push({ label: "Facet", value: facet }));
    datasetFacets.forEach((facet) =>
      chips.push({ label: "Dataset", value: DATASET_LABELS.get(facet) ?? facet }),
    );
    variantFacets.forEach((facet) =>
      chips.push({ label: "Variant", value: VARIANT_LABELS.get(facet) ?? facet }),
    );
    if (dateStart || dateEnd) {
      chips.push({ label: "Date", value: `${dateStart || "…"} – ${dateEnd || "…"}` });
    }
    if (includeVariants) chips.push({ label: "Variants", value: "Included" });
    if (includeDisputed) chips.push({ label: "Disputed", value: "Included" });
    if (!presetIsCustom) {
      const presetLabel =
        MODE_PRESETS.find((candidate) => candidate.value === presetSelection)?.label ??
        presetSelection;
      chips.push({ label: "Preset", value: presetLabel });
    }
    return chips;
  }, [
    author,
    collection,
    collectionFacets,
    datasetFacets,
    variantFacets,
    dateEnd,
    dateStart,
    includeDisputed,
    includeVariants,
    presetIsCustom,
    presetSelection,
    sourceType,
    theologicalTradition,
    topicDomain,
  ]);

  const queryTokens = useMemo(() => {
    return query
      .split(/\s+/)
      .map((token) => token.trim())
      .filter(Boolean);
  }, [query]);

  const applyResponseToState = useCallback(
    (payload: SearchResponse | null, nextSortKey?: string | null) => {
      const grouped = groupResults(payload);
      const sortedGroups = sortDocumentGroups(grouped, nextSortKey ?? sortKey);
      setGroups(sortedGroups);
    },
    [sortKey],
  );

  const runSearch = useCallback(
    async (filters: SearchFilters) => {
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
          applyResponseToState(payload);
          renderEnd = perf ? perf.now() : null;
          success = true;
        }
      } catch (fetchError) {
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
    [applyResponseToState],
  );

  const handleSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const filters = currentFilters;

    updateUrlForFilters(filters);
    await runSearch(filters);
  };

  const applyFilters = useCallback(
    (filters: SearchFilters) => {
      setQuery(filters.query);
      setOsis(filters.osis);
      setCollection(filters.collection);
      setAuthor(filters.author);
      setSourceType(filters.sourceType);
      setTheologicalTradition(filters.theologicalTradition);
      setTopicDomain(filters.topicDomain);
      setCollectionFacets([...filters.collectionFacets]);
      setDatasetFacets([...filters.datasetFacets]);
      setVariantFacets([...filters.variantFacets]);
      setDateStart(filters.dateStart);
      setDateEnd(filters.dateEnd);
      setIncludeVariants(filters.includeVariants);
      setIncludeDisputed(filters.includeDisputed);
      setPresetSelection(filters.preset || CUSTOM_PRESET_VALUE);
    },
    [],
  );

  const handlePresetChange = useCallback(
    (value: string) => {
      setPresetSelection(value);
      if (value === CUSTOM_PRESET_VALUE || value === "") {
        return;
      }
      const preset = MODE_PRESETS.find((option) => option.value === value);
      if (preset?.filters) {
        const nextFilters = normalizeFiltersFromPartial({
          ...currentFilters,
          ...preset.filters,
          preset: preset.value,
        });
        applyFilters(nextFilters);
        skipNextHydratedSearchRef.current = true;
        const nextQuery = serializeSearchParams(nextFilters);
        router.replace(`/search${nextQuery ? `?${nextQuery}` : ""}`, { scroll: false });
      }
    },
    [applyFilters, currentFilters, router],
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
      setSavedSearches((current) => {
        const existingIndex = current.findIndex((item) => item.name === trimmedName);
        if (existingIndex >= 0) {
          const updated = [...current];
          updated[existingIndex] = nextSearch;
          return updated;
        }
        return [...current, nextSearch].sort((a, b) => b.createdAt - a.createdAt);
      });
      setSavedSearchName("");
    },
    [currentFilters, savedSearchName],
  );

  const handleApplySavedSearch = useCallback(
    async (saved: SavedSearch) => {
      applyFilters(saved.filters);
      updateUrlForFilters(saved.filters);
      await runSearch(saved.filters);
    },
    [applyFilters, runSearch, updateUrlForFilters],
  );

  const handleDeleteSavedSearch = useCallback((id: string) => {
    setSavedSearches((current) => current.filter((saved) => saved.id !== id));
  }, []);

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
    };
  }, [diffSelection, groups]);

  const activePreset = useMemo(() => {
    const value = presetIsCustom ? CUSTOM_PRESET_VALUE : presetSelection;
    return MODE_PRESETS.find((candidate) => candidate.value === value);
  }, [presetIsCustom, presetSelection]);

  const handleGuidedPassageChip = useCallback(() => {
    osisInputRef.current?.focus();
    setOsis((current) => (current ? current : "John.1.1-5"));
  }, []);

  const handleGuidedTopicChip = useCallback(() => {
    queryInputRef.current?.focus();
    setQuery((current) => (current ? current : "atonement theology"));
  }, []);

  const handleShowErrorDetails = useCallback(() => {
    if (!error || !lastSearchFilters) {
      return;
    }

    const { chips, description } = formatSavedSearchFilters(lastSearchFilters);
    const metadata = chips.map((chip) => chip.text);
    const message = `Search failed${description ? ` for: ${description}` : ""}`;

    void emitTelemetry(
      [
        {
          event: "search.error.details",
          durationMs: 0,
          metadata: { chips: metadata, message, traceId: error.traceId },
        },
      ],
      { page: "search" },
    );
  }, [error, lastSearchFilters]);

  const handlePassageClick = useCallback(
    (result: SearchResult) => {
      if (!lastSearchFilters) {
        return;
      }
      const event: FeedbackEventInput = {
        action: "click",
        documentId: result.document_id,
        passageId: result.id,
        query: lastSearchFilters.query,
        rank: result.document_rank ?? null,
        score: result.score ?? null,
        confidence: result.retriever_score ?? null,
      };
      void submitFeedback(event);
    },
    [lastSearchFilters],
  );

  const handleRetrySearch = useCallback(() => {
    if (!lastSearchFilters) {
      return;
    }
    void runSearch(lastSearchFilters);
  }, [lastSearchFilters, runSearch]);

  useEffect(() => {
    applyResponseToState(initialResponse, sortKey);
  }, [applyResponseToState, initialResponse, sortKey]);

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
    const filters = parseSearchParams(searchParams);
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
  }, [arraysEqual, runSearch, searchParams]);

  useEffect(() => {
    setGroups((currentGroups) => sortDocumentGroups(currentGroups, sortKey));
  }, [sortKey]);

  useEffect(() => {
    setDiffSelection((current) =>
      current.filter((id) => groups.some((group) => group.documentId === id)),
    );
  }, [groups]);

  return (
    <section aria-labelledby="search-heading" style={{ display: "grid", gap: "1.5rem" }}>
      <h1 id="search-heading" style={{ fontSize: "2rem", margin: 0 }}>
        Explore the Theo knowledge base
      </h1>

      <div style={{ display: "grid", gap: "1rem" }}>
        <SearchFiltersForm
          query={query}
          osis={osis}
          collection={collection}
          author={author}
          sourceType={sourceType}
          theologicalTradition={theologicalTradition}
          topicDomain={topicDomain}
          collectionFacets={collectionFacets}
          datasetFacets={datasetFacets}
          variantFacets={variantFacets}
          dateStart={dateStart}
          dateEnd={dateEnd}
          includeVariants={includeVariants}
          includeDisputed={includeDisputed}
          isAdvancedUi={isAdvancedUi}
          isBeginnerMode={isBeginnerMode}
          isSearching={isSearching}
          presetSelection={presetSelection}
          presetIsCustom={presetIsCustom}
          modePresets={MODE_PRESETS}
          sourceOptions={SOURCE_OPTIONS}
          traditionOptions={TRADITION_OPTIONS}
          domainOptions={DOMAIN_OPTIONS}
          collectionFacetOptions={COLLECTION_FACETS}
          datasetFilters={DATASET_FILTERS}
          variantFilters={VARIANT_FILTERS}
          activePreset={activePreset ?? null}
          queryInputRef={queryInputRef}
          osisInputRef={osisInputRef}
          onSubmit={handleSearch}
          onQueryChange={setQuery}
          onOsisChange={setOsis}
          onCollectionChange={(value) => {
            setCollection(value);
            markPresetAsCustom();
          }}
          onAuthorChange={(value) => {
            setAuthor(value);
            markPresetAsCustom();
          }}
          onSourceTypeChange={(value) => {
            setSourceType(value);
            markPresetAsCustom();
          }}
          onTraditionChange={(value) => {
            setTheologicalTradition(value);
            markPresetAsCustom();
          }}
          onTopicDomainChange={(value) => {
            setTopicDomain(value);
            markPresetAsCustom();
          }}
          onDateStartChange={(value) => {
            setDateStart(value);
            markPresetAsCustom();
          }}
          onDateEndChange={(value) => {
            setDateEnd(value);
            markPresetAsCustom();
          }}
          onIncludeVariantsChange={(value) => {
            setIncludeVariants(value);
            markPresetAsCustom();
          }}
          onIncludeDisputedChange={(value) => {
            setIncludeDisputed(value);
            markPresetAsCustom();
          }}
          onToggleCollectionFacet={(facet) => {
            setCollectionFacets((current) => {
              const next = current.includes(facet)
                ? current.filter((value) => value !== facet)
                : [...current, facet];
              markPresetAsCustom();
              return next;
            });
          }}
          onToggleDatasetFacet={(facet) => {
            setDatasetFacets((current) => {
              const next = current.includes(facet)
                ? current.filter((value) => value !== facet)
                : [...current, facet];
              markPresetAsCustom();
              return next;
            });
          }}
          onToggleVariantFacet={(facet) => {
            setVariantFacets((current) => {
              const next = current.includes(facet)
                ? current.filter((value) => value !== facet)
                : [...current, facet];
              markPresetAsCustom();
              return next;
            });
          }}
          onPresetChange={handlePresetChange}
          onGuidedPassage={handleGuidedPassageChip}
          onGuidedTopic={handleGuidedTopicChip}
        />

        {filterChips.length > 0 && (
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            {filterChips.map((chip) => (
              <span
                key={`${chip.label}-${chip.value}`}
                style={{
                  background: "#e8eef9",
                  borderRadius: "999px",
                  padding: "0.25rem 0.75rem",
                  fontSize: "0.85rem",
                }}
              >
                <strong>{chip.label}:</strong> {chip.value}
              </span>
            ))}
          </div>
        )}
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: "1rem", alignItems: "center" }}>
        <SortControls value={sortKey} onChange={setSortKey} />
        <UiModeToggle mode={uiMode} onChange={setUiMode} />
      </div>

      {isAdvancedUi ? (
        <SavedSearchesPanel
          savedSearches={savedSearches}
          savedSearchName={savedSearchName}
          onNameChange={setSavedSearchName}
          onSubmit={handleSavedSearchSubmit}
          onApply={handleApplySavedSearch}
          onDelete={handleDeleteSavedSearch}
          formatFilters={formatSavedSearchFilters}
        />
      ) : (
        <details
          style={{
            border: "1px solid #cbd5f5",
            borderRadius: "0.75rem",
            padding: "0.75rem 1rem",
            background: "#f8fafc",
          }}
        >
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>Saved searches</summary>
          <p style={{ margin: "0.75rem 0", fontSize: "0.9rem", color: "#475569" }}>
            Expand to store or recall presets. Saved searches remember every active filter.
          </p>
          <SavedSearchesPanel
            savedSearches={savedSearches}
            savedSearchName={savedSearchName}
            onNameChange={setSavedSearchName}
            onSubmit={handleSavedSearchSubmit}
            onApply={handleApplySavedSearch}
            onDelete={handleDeleteSavedSearch}
            formatFilters={formatSavedSearchFilters}
          />
        </details>
      )}

      {rerankerName && (
        <div style={{ marginBottom: "1rem" }}>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.35rem",
              background: "#ecfdf5",
              color: "#047857",
              borderRadius: "999px",
              padding: "0.25rem 0.75rem",
              fontSize: "0.85rem",
              fontWeight: 600,
            }}
          >
            <span
              aria-hidden="true"
              style={{
                display: "inline-block",
                width: "0.5rem",
                height: "0.5rem",
                borderRadius: "999px",
                background: "#10b981",
              }}
            />
            Reranked by {rerankerName}
          </span>
        </div>
      )}

      <DiffWorkspace
        diffSelection={diffSelection}
        diffSummary={diffSummary}
        onClear={clearDiffSelection}
      />

      {isSearching && <p role="status">Searching.</p>}
      {error && (
        <div style={{ marginTop: "1rem" }}>
          <ErrorCallout
            message={error.message}
            traceId={error.traceId}
            onRetry={handleRetrySearch}
            onShowDetails={handleShowErrorDetails}
          />
        </div>
      )}
      {!isSearching && hasSearched && !error && groups.length === 0 && (
        <p>No results found for the current query.</p>
      )}

      <SearchResultsList
        groups={groups}
        activeActionsGroupId={activeActionsGroupId}
        onActiveChange={setActiveActionsGroupId}
        onExportGroup={handleExportGroup}
        onToggleDiffGroup={handleToggleDiffGroup}
        diffSelection={diffSelection}
        showAdvancedHints={isAdvancedUi}
        formatAnchor={formatAnchor}
        buildPassageLink={buildPassageLink}
        highlightTokens={(text) => highlightTokens(text, queryTokens)}
        onPassageClick={handlePassageClick}
      />
    </section>
  );
}

export {
  CUSTOM_PRESET_VALUE,
  DATASET_FILTERS,
  DATASET_LABELS,
  DOMAIN_LABELS,
  DOMAIN_OPTIONS,
  MODE_PRESETS,
  SAVED_SEARCH_CHIP_CONTAINER_STYLE,
  SAVED_SEARCH_CHIP_STYLE,
  SOURCE_LABELS,
  SOURCE_OPTIONS,
  TRADITION_LABELS,
  TRADITION_OPTIONS,
  VARIANT_FILTERS,
  VISUALLY_HIDDEN_STYLES,
};
