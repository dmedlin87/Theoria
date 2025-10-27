"use client";

import { useMemo } from "react";
import type { SearchFilters } from "../searchParams";

const SOURCE_LABELS = new Map([
  ["pdf", "PDF"],
  ["markdown", "Markdown"],
  ["youtube", "YouTube"],
  ["transcript", "Transcript"],
]);

const TRADITION_LABELS = new Map([
  ["anglican", "Anglican Communion"],
  ["baptist", "Baptist"],
  ["catholic", "Roman Catholic"],
  ["orthodox", "Eastern Orthodox"],
  ["reformed", "Reformed"],
  ["wesleyan", "Wesleyan/Methodist"],
]);

const DOMAIN_LABELS = new Map([
  ["christology", "Christology"],
  ["soteriology", "Soteriology"],
  ["ecclesiology", "Ecclesiology"],
  ["sacramental", "Sacramental Theology"],
  ["biblical-theology", "Biblical Theology"],
  ["ethics", "Christian Ethics"],
]);

const DATASET_LABELS = new Map([
  ["dss", "Dead Sea Scrolls"],
  ["nag-hammadi", "Nag Hammadi Codices"],
]);

const VARIANT_LABELS = new Map([
  ["disputed", "Disputed readings"],
  ["harmonized", "Harmonized expansions"],
  ["orthographic", "Orthographic shifts"],
]);

interface FilterChipsProps {
  filters: SearchFilters;
  onRemoveFilter: (key: keyof SearchFilters, value?: string) => void;
}

export default function FilterChips({ filters, onRemoveFilter }: FilterChipsProps): JSX.Element {
  const chips = useMemo(() => {
    const result: Array<{ key: keyof SearchFilters; label: string; value: string | null }> = [];

    if (filters.collection) {
      result.push({ key: "collection", label: "Collection", value: filters.collection });
    }
    if (filters.author) {
      result.push({ key: "author", label: "Author", value: filters.author });
    }
    if (filters.sourceType) {
      const label = SOURCE_LABELS.get(filters.sourceType) ?? filters.sourceType;
      result.push({ key: "sourceType", label: "Source", value: label });
    }
    if (filters.theologicalTradition) {
      const label = TRADITION_LABELS.get(filters.theologicalTradition) ?? filters.theologicalTradition;
      result.push({ key: "theologicalTradition", label: "Tradition", value: label });
    }
    if (filters.topicDomain) {
      const label = DOMAIN_LABELS.get(filters.topicDomain) ?? filters.topicDomain;
      result.push({ key: "topicDomain", label: "Topic", value: label });
    }

    filters.collectionFacets.forEach((facet) => {
      result.push({ key: "collectionFacets", label: "Facet", value: facet });
    });

    filters.datasetFacets.forEach((facet) => {
      const label = DATASET_LABELS.get(facet) ?? facet;
      result.push({ key: "datasetFacets", label: "Dataset", value: label });
    });

    filters.variantFacets.forEach((facet) => {
      const label = VARIANT_LABELS.get(facet) ?? facet;
      result.push({ key: "variantFacets", label: "Variant", value: label });
    });

    if (filters.dateStart || filters.dateEnd) {
      const dateValue = `${filters.dateStart || "…"} – ${filters.dateEnd || "…"}`;
      result.push({ key: "dateStart", label: "Date", value: dateValue });
    }

    if (filters.includeVariants) {
      result.push({ key: "includeVariants", label: "Variants", value: "Included" });
    }

    if (filters.includeDisputed) {
      result.push({ key: "includeDisputed", label: "Disputed", value: "Included" });
    }

    return result;
  }, [filters]);

  if (chips.length === 0) {
    return <></>;
  }

  return (
    <div className="stack-sm">
      <div className="cluster-sm">
        {chips.map((chip, index) => (
          <div key={`${chip.key}-${chip.value}-${index}`} className="chip chip-removable">
            <span className="text-sm">
              <strong className="font-semibold">{chip.label}:</strong> {chip.value}
            </span>
            <button
              type="button"
              className="chip__remove"
              onClick={() => onRemoveFilter(chip.key, chip.value || undefined)}
              aria-label={`Remove ${chip.label} filter`}
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
