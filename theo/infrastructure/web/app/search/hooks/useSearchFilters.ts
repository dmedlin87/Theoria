import { useCallback, useMemo, useState } from "react";
import type { SearchFilters } from "../searchParams";

const CUSTOM_PRESET_VALUE = "custom";

export function useSearchFilters(initialFilters: SearchFilters) {
  const [query, setQuery] = useState<string>(initialFilters.query);
  const [osis, setOsis] = useState<string>(initialFilters.osis);
  const [collection, setCollection] = useState<string>(initialFilters.collection);
  const [author, setAuthor] = useState<string>(initialFilters.author);
  const [sourceType, setSourceType] = useState<string>(initialFilters.sourceType);
  const [theologicalTradition, setTheologicalTradition] = useState<string>(
    initialFilters.theologicalTradition
  );
  const [topicDomain, setTopicDomain] = useState<string>(initialFilters.topicDomain);
  const [collectionFacets, setCollectionFacets] = useState<string[]>([...initialFilters.collectionFacets]);
  const [datasetFacets, setDatasetFacets] = useState<string[]>([...initialFilters.datasetFacets]);
  const [variantFacets, setVariantFacets] = useState<string[]>([...initialFilters.variantFacets]);
  const [dateStart, setDateStart] = useState<string>(initialFilters.dateStart);
  const [dateEnd, setDateEnd] = useState<string>(initialFilters.dateEnd);
  const [includeVariants, setIncludeVariants] = useState<boolean>(initialFilters.includeVariants);
  const [includeDisputed, setIncludeDisputed] = useState<boolean>(initialFilters.includeDisputed);
  const [presetSelection, setPresetSelection] = useState<string>(
    initialFilters.preset || CUSTOM_PRESET_VALUE
  );

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
      preset: presetSelection === CUSTOM_PRESET_VALUE ? "" : presetSelection.trim(),
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
      presetSelection,
      query,
      sourceType,
    ]
  );

  const markPresetAsCustom = useCallback(() => {
    setPresetSelection((current) =>
      current === CUSTOM_PRESET_VALUE ? current : CUSTOM_PRESET_VALUE
    );
  }, []);

  const applyFilters = useCallback((filters: SearchFilters) => {
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
  }, []);

  const resetFilters = useCallback(() => {
    setQuery("");
    setOsis("");
    setCollection("");
    setAuthor("");
    setSourceType("");
    setTheologicalTradition("");
    setTopicDomain("");
    setCollectionFacets([]);
    setDatasetFacets([]);
    setVariantFacets([]);
    setDateStart("");
    setDateEnd("");
    setIncludeVariants(false);
    setIncludeDisputed(false);
    setPresetSelection(CUSTOM_PRESET_VALUE);
  }, []);

  const toggleFacet = useCallback(
    (facet: string) => {
      setCollectionFacets((current) =>
        current.includes(facet)
          ? current.filter((value) => value !== facet)
          : [...current, facet]
      );
      markPresetAsCustom();
    },
    [markPresetAsCustom]
  );

  const toggleDatasetFacet = useCallback(
    (facet: string) => {
      setDatasetFacets((current) =>
        current.includes(facet)
          ? current.filter((value) => value !== facet)
          : [...current, facet]
      );
      markPresetAsCustom();
    },
    [markPresetAsCustom]
  );

  const toggleVariantFacet = useCallback(
    (facet: string) => {
      setVariantFacets((current) =>
        current.includes(facet)
          ? current.filter((value) => value !== facet)
          : [...current, facet]
      );
      markPresetAsCustom();
    },
    [markPresetAsCustom]
  );

  return {
    filters: {
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
    setters: {
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
    currentFilters,
    applyFilters,
    resetFilters,
    toggleFacet,
    toggleDatasetFacet,
    toggleVariantFacet,
    markPresetAsCustom,
  };
}
