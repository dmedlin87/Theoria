import { useCallback, useMemo, useState } from "react";

import type { SearchFilters } from "../../searchParams";
import {
  CUSTOM_PRESET_VALUE,
  DATASET_LABELS,
  MODE_PRESETS,
  VARIANT_LABELS,
} from "./constants";

export type SearchFiltersState = {
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
  presetSelection: string;
};

export type UseSearchFiltersStateResult = {
  state: SearchFiltersState;
  setState: {
    setQuery: (value: string) => void;
    setOsis: (value: string) => void;
    setCollection: (value: string) => void;
    setAuthor: (value: string) => void;
    setSourceType: (value: string) => void;
    setTheologicalTradition: (value: string) => void;
    setTopicDomain: (value: string) => void;
    setCollectionFacets: (value: string[]) => void;
    setDatasetFacets: (value: string[]) => void;
    setVariantFacets: (value: string[]) => void;
    setDateStart: (value: string) => void;
    setDateEnd: (value: string) => void;
    setIncludeVariants: (value: boolean) => void;
    setIncludeDisputed: (value: boolean) => void;
    setPresetSelection: (value: string) => void;
  };
  derived: {
    presetIsCustom: boolean;
    currentFilters: SearchFilters;
    filterChips: { label: string; value: string }[];
    queryTokens: string[];
  };
  actions: {
    markPresetAsCustom: () => void;
    applyFilters: (filters: SearchFilters) => void;
    toggleCollectionFacet: (facet: string) => void;
    toggleDatasetFacet: (facet: string) => void;
    toggleVariantFacet: (facet: string) => void;
  };
};

export function useSearchFiltersState(initialFilters: SearchFilters): UseSearchFiltersStateResult {
  const [query, setQuery] = useState<string>(() => initialFilters.query);
  const [osis, setOsis] = useState<string>(() => initialFilters.osis);
  const [collection, setCollection] = useState<string>(() => initialFilters.collection);
  const [author, setAuthor] = useState<string>(() => initialFilters.author);
  const [sourceType, setSourceType] = useState<string>(() => initialFilters.sourceType);
  const [theologicalTradition, setTheologicalTradition] = useState<string>(
    () => initialFilters.theologicalTradition,
  );
  const [topicDomain, setTopicDomain] = useState<string>(() => initialFilters.topicDomain);
  const [collectionFacets, setCollectionFacets] = useState<string[]>(
    () => [...initialFilters.collectionFacets],
  );
  const [datasetFacets, setDatasetFacets] = useState<string[]>(
    () => [...initialFilters.datasetFacets],
  );
  const [variantFacets, setVariantFacets] = useState<string[]>(
    () => [...initialFilters.variantFacets],
  );
  const [dateStart, setDateStart] = useState<string>(() => initialFilters.dateStart);
  const [dateEnd, setDateEnd] = useState<string>(() => initialFilters.dateEnd);
  const [includeVariants, setIncludeVariants] = useState<boolean>(
    () => initialFilters.includeVariants,
  );
  const [includeDisputed, setIncludeDisputed] = useState<boolean>(
    () => initialFilters.includeDisputed,
  );
  const [presetSelection, setPresetSelection] = useState<string>(
    () => initialFilters.preset || CUSTOM_PRESET_VALUE,
  );

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
    [],
  );

  const toggleCollectionFacet = useCallback(
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

  return {
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
  };
}
