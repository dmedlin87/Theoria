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
} from "react";

import ErrorCallout from "../components/ErrorCallout";
import UiModeToggle from "../components/UiModeToggle";
import { buildPassageLink, formatAnchor } from "../lib/api";
import { type ErrorDetails, parseErrorResponse } from "../lib/errorUtils";
import type { components } from "../lib/generated/api";
import { emitTelemetry, submitFeedback } from "../lib/telemetry";
import type { FeedbackEventInput } from "../lib/telemetry";
import { usePersistentSort } from "../lib/usePersistentSort";
import { useUiModePreference } from "../lib/useUiModePreference";
import { sortDocumentGroups, SortableDocumentGroup } from "./groupSorting";
import { SortControls } from "./SortControls";
import {
  parseSearchParams,
  serializeSearchParams,
  type SearchFilters,
} from "./searchParams";

const SOURCE_OPTIONS = [
  { label: "Any source", value: "" },
  { label: "PDF", value: "pdf" },
  { label: "Markdown", value: "markdown" },
  { label: "YouTube", value: "youtube" },
  { label: "Transcript", value: "transcript" },
];

const TRADITION_OPTIONS = [
  { label: "Any tradition", value: "" },
  { label: "Anglican Communion", value: "anglican" },
  { label: "Baptist", value: "baptist" },
  { label: "Roman Catholic", value: "catholic" },
  { label: "Eastern Orthodox", value: "orthodox" },
  { label: "Reformed", value: "reformed" },
  { label: "Wesleyan/Methodist", value: "wesleyan" },
];

const DOMAIN_OPTIONS = [
  { label: "Any topic", value: "" },
  { label: "Christology", value: "christology" },
  { label: "Soteriology", value: "soteriology" },
  { label: "Ecclesiology", value: "ecclesiology" },
  { label: "Sacramental Theology", value: "sacramental" },
  { label: "Biblical Theology", value: "biblical-theology" },
  { label: "Christian Ethics", value: "ethics" },
];

const COLLECTION_FACETS = [
  "Dead Sea Scrolls",
  "Nag Hammadi",
  "Church Fathers",
  "Second Temple",
];

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
];

const VARIANT_FILTERS = [
  { label: "Disputed readings", value: "disputed" },
  { label: "Harmonized expansions", value: "harmonized" },
  { label: "Orthographic shifts", value: "orthographic" },
];

const DATASET_LABELS = new Map(DATASET_FILTERS.map((option) => [option.value, option.label] as const));
const VARIANT_LABELS = new Map(VARIANT_FILTERS.map((option) => [option.value, option.label] as const));

const CUSTOM_PRESET_VALUE = "custom";
const SAVED_SEARCH_STORAGE_KEY = "theo.search.saved";

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

type SavedSearch = {
  id: string;
  name: string;
  filters: SearchFilters;
  createdAt: number;
};

type SearchResult = components["schemas"]["HybridSearchResult"];

type SearchResponse = components["schemas"]["HybridSearchResponse"];

type DocumentGroup = SortableDocumentGroup & {
  documentId: string;
  passages: SearchResult[];
};

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

export default function SearchPage(): JSX.Element {
  const router = useRouter();
  const searchParams = useSearchParams();
  const skipNextHydratedSearchRef = useRef(false);
  const [uiMode, setUiMode] = useUiModePreference();
  const isAdvancedUi = uiMode === "advanced";
  const [query, setQuery] = useState("");
  const [osis, setOsis] = useState("");
  const [collection, setCollection] = useState("");
  const [author, setAuthor] = useState("");
  const [sourceType, setSourceType] = useState("");
  const [theologicalTradition, setTheologicalTradition] = useState("");
  const [topicDomain, setTopicDomain] = useState("");
  const [collectionFacets, setCollectionFacets] = useState<string[]>([]);
  const [datasetFacets, setDatasetFacets] = useState<string[]>([]);
  const [variantFacets, setVariantFacets] = useState<string[]>([]);
  const [dateStart, setDateStart] = useState("");
  const [dateEnd, setDateEnd] = useState("");
  const [includeVariants, setIncludeVariants] = useState(false);
  const [includeDisputed, setIncludeDisputed] = useState(false);
  const [presetSelection, setPresetSelection] = useState<string>(CUSTOM_PRESET_VALUE);
  const [groups, setGroups] = useState<DocumentGroup[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<ErrorDetails | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [sortKey, setSortKey] = usePersistentSort();
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>([]);
  const [savedSearchName, setSavedSearchName] = useState("");
  const [diffSelection, setDiffSelection] = useState<string[]>([]);
  const [lastSearchFilters, setLastSearchFilters] = useState<SearchFilters | null>(null);
  const [rerankerName, setRerankerName] = useState<string | null>(null);

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
          const grouped = new Map<string, DocumentGroup>();
          for (const result of payload.results ?? []) {
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
          const sortedGroups = sortDocumentGroups(Array.from(grouped.values()), sortKey);
          setGroups(sortedGroups);
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
    [sortKey],
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
      setPresetSelection(filters.preset ? filters.preset : CUSTOM_PRESET_VALUE);
    },
    [author, collection, collectionFacets, datasetFacets, includeDisputed, includeVariants, sourceType, theologicalTradition, topicDomain, variantFacets, dateEnd, dateStart, presetIsCustom, presetSelection],
  );

  const handleShowErrorDetails = useCallback((traceId: string | null) => {
    const detailMessage = traceId
      ? `Trace ID: ${traceId}`
      : "No additional trace information is available.";
    window.alert(detailMessage);
  }, []);

  const handleRetrySearch = useCallback(() => {
    if (lastSearchFilters) {
      void runSearch(lastSearchFilters);
    }
  }, [lastSearchFilters, runSearch]);

  const handlePassageClick = useCallback(
    (result: SearchResult) => {
      const queryValue = (
        lastSearchFilters?.query ?? currentFilters.query ?? ""
      ).trim();
      const rerankScore =
        typeof result.reranker_score === "number" ? result.reranker_score : undefined;
      const passageScore =
        typeof result.score === "number" ? result.score : undefined;
      const retrieverScore =
        typeof result.retriever_score === "number" ? result.retriever_score : undefined;
      const payload = {
        action: "click",
        documentId: result.document_id,
        passageId: result.id,
        ...(typeof result.rank === "number" ? { rank: result.rank } : {}),
        ...(typeof rerankScore === "number"
          ? { score: rerankScore }
          : typeof passageScore === "number"
          ? { score: passageScore }
          : {}),
        ...(typeof retrieverScore === "number" ? { confidence: retrieverScore } : {}),
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
      return;
    }
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
    void runSearch(nextFilters);
    },
    [applyFilters, currentFilters, runSearch, updateUrlForFilters],
  );

  const toggleFacet = useCallback(
    (facet: string) => {
      setCollectionFacets((current) => {
        const next = current.includes(facet)
          ? current.filter((value) => value !== facet)
          : [...current, facet];
        markPresetAsCustom();
        return next;
      });
    },
    [markPresetAsCustom],
  );

  const toggleDatasetFacet = useCallback(
    (facet: string) => {
      setDatasetFacets((current) => {
        const next = current.includes(facet)
          ? current.filter((value) => value !== facet)
          : [...current, facet];
        markPresetAsCustom();
        return next;
      });
    },
    [markPresetAsCustom],
  );

  const toggleVariantFacet = useCallback(
    (facet: string) => {
      setVariantFacets((current) => {
        const next = current.includes(facet)
          ? current.filter((value) => value !== facet)
          : [...current, facet];
        markPresetAsCustom();
        return next;
      });
    },
    [markPresetAsCustom],
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

  const diffSummary = useMemo(() => {
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
      shared: first.passages.length + second.passages.length - uniqueToFirst.length - uniqueToSecond.length,
    };
  }, [diffSelection, groups]);

  const activePreset = useMemo(() => {
    const value = presetIsCustom ? CUSTOM_PRESET_VALUE : presetSelection;
    return MODE_PRESETS.find((candidate) => candidate.value === value);
  }, [presetIsCustom, presetSelection]);

  const advancedFilterControls = (
    <div style={{ display: "grid", gap: "0.75rem" }}>
      <div>
        <label style={{ display: "block" }}>
          Mode preset
          <select
            name="preset"
            value={presetIsCustom ? CUSTOM_PRESET_VALUE : presetSelection}
            onChange={(event) => handlePresetChange(event.target.value)}
            style={{ width: "100%" }}
          >
            {MODE_PRESETS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        {activePreset?.description && (
          <p style={{ margin: "0.35rem 0 0", fontSize: "0.85rem", color: "#555" }}>
            {activePreset.description}
          </p>
        )}
      </div>
      <label style={{ display: "block" }}>
        Collection
        <input
          name="collection"
          type="text"
          value={collection}
          onChange={(event) => {
            setCollection(event.target.value);
            markPresetAsCustom();
          }}
          placeholder="Gospels"
          style={{ width: "100%" }}
        />
      </label>
      <label style={{ display: "block" }}>
        Author
        <input
          name="author"
          type="text"
          value={author}
          onChange={(event) => {
            setAuthor(event.target.value);
            markPresetAsCustom();
          }}
          placeholder="Jane Doe"
          style={{ width: "100%" }}
        />
      </label>
      <label style={{ display: "block" }}>
        Source type
        <select
          name="source_type"
          value={sourceType}
          onChange={(event) => {
            setSourceType(event.target.value);
            markPresetAsCustom();
          }}
          style={{ width: "100%" }}
        >
          {SOURCE_OPTIONS.map((option) => (
            <option key={option.value || "any"} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <label style={{ display: "block" }}>
        Theological tradition
        <select
          name="theological_tradition"
          value={theologicalTradition}
          onChange={(event) => {
            setTheologicalTradition(event.target.value);
            markPresetAsCustom();
          }}
          style={{ width: "100%" }}
        >
          {TRADITION_OPTIONS.map((option) => (
            <option key={option.value || "any"} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <label style={{ display: "block" }}>
        Topic domain
        <select
          name="topic_domain"
          value={topicDomain}
          onChange={(event) => {
            setTopicDomain(event.target.value);
            markPresetAsCustom();
          }}
          style={{ width: "100%" }}
        >
          {DOMAIN_OPTIONS.map((option) => (
            <option key={option.value || "any"} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <fieldset
        style={{
          border: "1px solid #e2e8f0",
          borderRadius: "0.5rem",
          padding: "0.75rem",
        }}
      >
        <legend style={{ padding: "0 0.35rem" }}>Collection facets</legend>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem" }}>
          {COLLECTION_FACETS.map((facet) => (
            <label key={facet} style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
              <input
                type="checkbox"
                checked={collectionFacets.includes(facet)}
                onChange={() => toggleFacet(facet)}
              />
              {facet}
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset
        style={{
          border: "1px solid #e2e8f0",
          borderRadius: "0.5rem",
          padding: "0.75rem",
        }}
      >
        <legend style={{ padding: "0 0.35rem" }}>Dataset facets</legend>
        <div style={{ display: "grid", gap: "0.5rem" }}>
          {DATASET_FILTERS.map((dataset) => {
            const isActive = datasetFacets.includes(dataset.value);
            return (
              <label
                key={dataset.value}
                style={{ display: "grid", gap: "0.1rem", alignItems: "flex-start" }}
              >
                <span style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
                  <input
                    type="checkbox"
                    checked={isActive}
                    onChange={() => toggleDatasetFacet(dataset.value)}
                  />
                  <strong>{dataset.label}</strong>
                </span>
                <span style={{ fontSize: "0.8rem", color: "#4b5563", marginLeft: "1.75rem" }}>
                  {dataset.description}
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>
      <fieldset
        style={{
          border: "1px solid #e2e8f0",
          borderRadius: "0.5rem",
          padding: "0.75rem",
        }}
      >
        <legend style={{ padding: "0 0.35rem" }}>Variant focus</legend>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem" }}>
          {VARIANT_FILTERS.map((variant) => (
            <label
              key={variant.value}
              style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}
            >
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
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem" }}>
        <label style={{ display: "block" }}>
          Date from
          <input
            type="date"
            name="date_start"
            value={dateStart}
            onChange={(event) => {
              setDateStart(event.target.value);
              markPresetAsCustom();
            }}
            style={{ width: "100%" }}
          />
        </label>
        <label style={{ display: "block" }}>
          Date to
          <input
            type="date"
            name="date_end"
            value={dateEnd}
            onChange={(event) => {
              setDateEnd(event.target.value);
              markPresetAsCustom();
            }}
            style={{ width: "100%" }}
          />
        </label>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "1rem" }}>
        <label style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
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
        <label style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
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

  useEffect(() => {
    try {
      const stored = localStorage.getItem(SAVED_SEARCH_STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as SavedSearch[];
        if (Array.isArray(parsed)) {
          setSavedSearches(parsed);
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
      <section>
        <h2>Search</h2>
      <p>Hybrid search with lexical, vector, and OSIS-aware filtering.</p>
      <div style={{ margin: "1.5rem 0" }}>
        <UiModeToggle mode={uiMode} onChange={setUiMode} />
      </div>

      <form
        onSubmit={handleSearch}
        aria-label="Search corpus"
        style={{ marginBottom: "1.5rem", display: "grid", gap: "1rem" }}
      >
        <div style={{ display: "grid", gap: "0.75rem" }}>
          <label style={{ display: "block" }}>
            Query
            <input
              name="q"
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search corpus"
              style={{ width: "100%" }}
            />
          </label>
          <label style={{ display: "block" }}>
            OSIS reference
            <input
              name="osis"
              type="text"
              value={osis}
              onChange={(event) => setOsis(event.target.value)}
              placeholder="John.1.1-5"
              style={{ width: "100%" }}
            />
          </label>
        </div>

        {!isAdvancedUi && (
          <p style={{ margin: 0, color: "#475569" }}>
            Simple mode shows only the essentials. Open the advanced panel for presets, guardrail filters, and facets.
          </p>
        )}

        {isAdvancedUi ? (
          <div>{advancedFilterControls}</div>
        ) : (
          <details
            style={{
              border: "1px solid #cbd5f5",
              borderRadius: "0.75rem",
              padding: "0.75rem 1rem",
              background: "#f8fafc",
            }}
          >
            <summary style={{ cursor: "pointer", fontWeight: 600 }}>
              Advanced filters & presets
            </summary>
            <p style={{ margin: "0.75rem 0", fontSize: "0.9rem", color: "#475569" }}>
              Expand when you need dataset facets, guardrail profiles, or saved presets.
            </p>
            {advancedFilterControls}
          </details>
        )}

        <button type="submit" style={{ marginTop: "0.5rem" }} disabled={isSearching}>
          {isSearching ? "Searching." : "Search"}
        </button>
      </form>


      <section aria-label="Saved searches" style={{ margin: "2rem 0" }}>
        <h3 style={{ marginBottom: "0.75rem" }}>Saved searches</h3>
        <form onSubmit={handleSavedSearchSubmit} style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <input
            type="text"
            value={savedSearchName}
            onChange={(event) => setSavedSearchName(event.target.value)}
            placeholder="Name this search"
            style={{ flex: "1 1 220px", minWidth: "200px" }}
          />
          <button type="submit" disabled={!savedSearchName.trim()}>
            Save current filters
          </button>
        </form>
        {savedSearches.length === 0 ? (
          <p style={{ marginTop: "0.75rem", fontSize: "0.9rem", color: "#555" }}>
            No saved searches yet. Configure filters and click save to store a preset.
          </p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: "0.75rem 0 0", display: "grid", gap: "0.5rem" }}>
            {savedSearches.map((saved) => (
              <li
                key={saved.id}
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "0.5rem",
                  alignItems: "center",
                  justifyContent: "space-between",
                  border: "1px solid #e2e8f0",
                  borderRadius: "0.5rem",
                  padding: "0.5rem 0.75rem",
                }}
              >
                <div>
                  <strong>{saved.name}</strong>
                  <p style={{ margin: "0.25rem 0 0", fontSize: "0.85rem", color: "#555" }}>
                    {serializeSearchParams(saved.filters)}
                  </p>
                </div>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <button type="button" onClick={() => void handleApplySavedSearch(saved)}>
                    Run
                  </button>
                  <button type="button" onClick={() => handleDeleteSavedSearch(saved.id)}>
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div style={{ margin: "1.5rem 0" }}>
        <SortControls value={sortKey} onChange={setSortKey} />
      </div>

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

      {filterChips.length > 0 && (
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "1rem" }}>
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

      {diffSelection.length > 0 && (
        <aside
          style={{
            margin: "1.5rem 0",
            padding: "1rem",
            border: "1px solid #cbd5f5",
            borderRadius: "0.75rem",
            background: "#f4f7ff",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem" }}>
            <h3 style={{ margin: 0 }}>Diff workspace</h3>
            <button type="button" onClick={clearDiffSelection}>
              Clear selection
            </button>
          </div>
          {diffSummary ? (
            <div style={{ marginTop: "0.75rem" }}>
              <p style={{ margin: "0 0 0.5rem" }}>
                Comparing <strong>{diffSummary.first.title}</strong> and <strong>{diffSummary.second.title}</strong>
              </p>
              <ul style={{ margin: 0, paddingLeft: "1.25rem" }}>
                <li>{diffSummary.first.passages.length} passages in first group ({diffSummary.uniqueToFirst.length} unique)</li>
                <li>{diffSummary.second.passages.length} passages in second group ({diffSummary.uniqueToSecond.length} unique)</li>
                <li>{diffSummary.shared} overlapping passages across both groups</li>
              </ul>
              {(diffSummary.uniqueToFirst.length > 0 || diffSummary.uniqueToSecond.length > 0) && (
                <div style={{ marginTop: "0.75rem", display: "grid", gap: "0.5rem" }}>
                  {diffSummary.uniqueToFirst.length > 0 && (
                    <p style={{ margin: 0 }}>
                      Unique to {diffSummary.first.title}: {diffSummary.uniqueToFirst.join(", ")}
                    </p>
                  )}
                  {diffSummary.uniqueToSecond.length > 0 && (
                    <p style={{ margin: 0 }}>
                      Unique to {diffSummary.second.title}: {diffSummary.uniqueToSecond.join(", ")}
                    </p>
                  )}
                </div>
              )}
            </div>
          ) : (
            <p style={{ marginTop: "0.75rem" }}>
              Select another group to compare. Up to two result groups can be diffed at once.
            </p>
          )}
        </aside>
      )}

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

      <div style={{ display: "grid", gap: "1rem" }}>
        {groups.map((group) => {
          const isSelectedForDiff = diffSelection.includes(group.documentId);
          const diffLabel = isSelectedForDiff
            ? "Remove from diff"
            : diffSelection.length >= 2
            ? "Replace in diff"
            : "Add to diff";
          return (
            <article
              key={group.documentId}
              style={{
                background: "#fff",
                borderRadius: "0.75rem",
                padding: "1.25rem",
                border: isSelectedForDiff ? "2px solid #3b82f6" : "1px solid #e2e8f0",
              }}
            >
              <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "1rem" }}>
                <div>
                  <h3 style={{ margin: "0 0 0.25rem" }}>{group.title}</h3>
                  {typeof group.rank === "number" && (
                    <p style={{ margin: 0 }}>Document rank #{group.rank}</p>
                  )}
                  {typeof group.score === "number" && (
                    <p style={{ margin: "0.25rem 0 0", fontSize: "0.85rem", color: "#555" }}>
                      Document score {group.score.toFixed(2)}
                    </p>
                  )}
                </div>
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  <button type="button" onClick={() => handleExportGroup(group)}>
                    Export JSON
                  </button>
                  <button type="button" onClick={() => handleToggleDiffGroup(group.documentId)}>
                    {diffLabel}
                  </button>
                </div>
              </header>
              <ul style={{ listStyle: "none", padding: 0, margin: "1rem 0 0", display: "grid", gap: "0.75rem" }}>
                {group.passages.map((result) => {
                  const anchorDescription = formatAnchor({
                    page_no: result.page_no ?? null,
                    t_start: result.t_start ?? null,
                    t_end: result.t_end ?? null,
                  });
                  return (
                    <li key={result.id} style={{ border: "1px solid #e2e8f0", borderRadius: "0.5rem", padding: "0.75rem" }}>
                      <div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem" }}>
                          <div>
                            {anchorDescription && <p style={{ margin: "0 0 0.25rem" }}>{anchorDescription}</p>}
                            {result.osis_ref && <p style={{ margin: 0 }}>OSIS: {result.osis_ref}</p>}
                          </div>
                          <Link
                            href={buildPassageLink(result.document_id, result.id, {
                              pageNo: result.page_no ?? null,
                              tStart: result.t_start ?? null,
                            })}
                            onClick={() => handlePassageClick(result)}
                            style={{ whiteSpace: "nowrap" }}
                          >
                            Open passage
                          </Link>
                        </div>
                        <p style={{ marginTop: "0.5rem" }}>{result.snippet}</p>
                        {Array.isArray(result.highlights) && result.highlights.length > 0 && (
                          <div style={{ marginTop: "0.75rem", display: "grid", gap: "0.5rem" }}>
                            {result.highlights.map((highlight) => (
                              <p
                                key={highlight}
                                style={{
                                  margin: 0,
                                  fontSize: "0.9rem",
                                  background: "#f6f8fb",
                                  padding: "0.5rem",
                                  borderRadius: "0.5rem",
                                }}
                              >
                                {highlightTokens(highlight, queryTokens)}
                              </p>
                            ))}
                          </div>
                        )}
                        {typeof result.score === "number" && (
                          <p style={{ marginTop: "0.5rem", fontSize: "0.85rem", color: "#555" }}>
                            Passage score {result.score.toFixed(2)}
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
