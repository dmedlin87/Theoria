"use client";

import type { FormEvent, MutableRefObject } from "react";

import type { SearchFilters } from "../searchParams";
import { CUSTOM_PRESET_VALUE } from "./SearchPageClient";

type ModePreset = {
  value: string;
  label: string;
  description: string;
  filters?: Partial<SearchFilters>;
};

type Option = { label: string; value: string };

type DatasetFilter = { label: string; value: string; description: string };

type VariantFilter = { label: string; value: string };

type SearchFiltersFormProps = {
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
  isAdvancedUi: boolean;
  isBeginnerMode: boolean;
  isSearching: boolean;
  presetSelection: string;
  presetIsCustom: boolean;
  modePresets: ModePreset[];
  sourceOptions: readonly Option[];
  traditionOptions: readonly Option[];
  domainOptions: readonly Option[];
  collectionFacetOptions: readonly string[];
  datasetFilters: readonly DatasetFilter[];
  variantFilters: readonly VariantFilter[];
  activePreset: ModePreset | null;
  queryInputRef: MutableRefObject<HTMLInputElement | null>;
  osisInputRef: MutableRefObject<HTMLInputElement | null>;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onQueryChange: (value: string) => void;
  onOsisChange: (value: string) => void;
  onCollectionChange: (value: string) => void;
  onAuthorChange: (value: string) => void;
  onSourceTypeChange: (value: string) => void;
  onTraditionChange: (value: string) => void;
  onTopicDomainChange: (value: string) => void;
  onDateStartChange: (value: string) => void;
  onDateEndChange: (value: string) => void;
  onIncludeVariantsChange: (value: boolean) => void;
  onIncludeDisputedChange: (value: boolean) => void;
  onToggleCollectionFacet: (facet: string) => void;
  onToggleDatasetFacet: (facet: string) => void;
  onToggleVariantFacet: (facet: string) => void;
  onPresetChange: (value: string) => void;
  onGuidedPassage: () => void;
  onGuidedTopic: () => void;
};

export default function SearchFiltersForm({
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
  isAdvancedUi,
  isBeginnerMode,
  isSearching,
  presetSelection,
  presetIsCustom,
  modePresets,
  sourceOptions,
  traditionOptions,
  domainOptions,
  collectionFacetOptions,
  datasetFilters,
  variantFilters,
  activePreset,
  queryInputRef,
  osisInputRef,
  onSubmit,
  onQueryChange,
  onOsisChange,
  onCollectionChange,
  onAuthorChange,
  onSourceTypeChange,
  onTraditionChange,
  onTopicDomainChange,
  onDateStartChange,
  onDateEndChange,
  onIncludeVariantsChange,
  onIncludeDisputedChange,
  onToggleCollectionFacet,
  onToggleDatasetFacet,
  onToggleVariantFacet,
  onPresetChange,
  onGuidedPassage,
  onGuidedTopic,
}: SearchFiltersFormProps): JSX.Element {
  const assignQueryRef = (element: HTMLInputElement | null) => {
    queryInputRef.current = element;
  };
  const assignOsisRef = (element: HTMLInputElement | null) => {
    osisInputRef.current = element;
  };

  const advancedControls = (
    <div style={{ display: "grid", gap: "0.75rem" }}>
      <div>
        <label style={{ display: "block" }}>
          Mode preset
          <select
            name="preset"
            value={presetIsCustom ? CUSTOM_PRESET_VALUE : presetSelection}
            onChange={(event) => onPresetChange(event.target.value)}
            style={{ width: "100%" }}
          >
            {modePresets.map((option) => (
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
          onChange={(event) => onCollectionChange(event.target.value)}
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
          onChange={(event) => onAuthorChange(event.target.value)}
          placeholder="Jane Doe"
          style={{ width: "100%" }}
        />
      </label>
      <label style={{ display: "block" }}>
        Source type
        <select
          name="source_type"
          value={sourceType}
          onChange={(event) => onSourceTypeChange(event.target.value)}
          style={{ width: "100%" }}
        >
          {sourceOptions.map((option) => (
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
          onChange={(event) => onTraditionChange(event.target.value)}
          style={{ width: "100%" }}
        >
          {traditionOptions.map((option) => (
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
          onChange={(event) => onTopicDomainChange(event.target.value)}
          style={{ width: "100%" }}
        >
          {domainOptions.map((option) => (
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
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
          {collectionFacetOptions.map((facet) => {
            const isChecked = collectionFacets.includes(facet);
            return (
              <label key={facet} style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={() => onToggleCollectionFacet(facet)}
                />
                {facet}
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
        <legend style={{ padding: "0 0.35rem" }}>Datasets</legend>
        <div style={{ display: "grid", gap: "0.5rem" }}>
          {datasetFilters.map((dataset) => {
            const isActive = datasetFacets.includes(dataset.value);
            return (
              <label key={dataset.value} style={{ display: "grid", gap: "0.25rem" }}>
                <span style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
                  <input
                    type="checkbox"
                    checked={isActive}
                    onChange={() => onToggleDatasetFacet(dataset.value)}
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
          {variantFilters.map((variant) => (
            <label
              key={variant.value}
              style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}
            >
              <input
                type="checkbox"
                checked={variantFacets.includes(variant.value)}
                onChange={() => onToggleVariantFacet(variant.value)}
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
            onChange={(event) => onDateStartChange(event.target.value)}
            style={{ width: "100%" }}
          />
        </label>
        <label style={{ display: "block" }}>
          Date to
          <input
            type="date"
            name="date_end"
            value={dateEnd}
            onChange={(event) => onDateEndChange(event.target.value)}
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
            onChange={(event) => onIncludeVariantsChange(event.target.checked)}
          />
          Include textual variants
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
          <input
            type="checkbox"
            name="disputed"
            checked={includeDisputed}
            onChange={(event) => onIncludeDisputedChange(event.target.checked)}
          />
          Include disputed readings
        </label>
      </div>
    </div>
  );

  return (
    <form
      onSubmit={onSubmit}
      aria-label="Search corpus"
      style={{ marginBottom: "1.5rem", display: "grid", gap: "1rem" }}
    >
      <div style={{ display: "grid", gap: "0.75rem" }}>
        <div
          aria-label="Guided search suggestions"
          style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}
        >
          <button
            type="button"
            onClick={onGuidedPassage}
            style={{
              border: "1px solid #cbd5f5",
              background: "#eef2ff",
              color: "#312e81",
              borderRadius: "999px",
              padding: "0.25rem 0.75rem",
              fontSize: "0.85rem",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Search by passage
          </button>
          <button
            type="button"
            onClick={onGuidedTopic}
            style={{
              border: "1px solid #cbd5f5",
              background: "#eef2ff",
              color: "#312e81",
              borderRadius: "999px",
              padding: "0.25rem 0.75rem",
              fontSize: "0.85rem",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Search by topic
          </button>
        </div>
        <label style={{ display: "block" }}>
          Query
          <input
            name="q"
            type="text"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Search corpus"
            style={{ width: "100%" }}
            ref={assignQueryRef}
          />
        </label>
        <label style={{ display: "block" }}>
          OSIS reference
          <input
            name="osis"
            type="text"
            value={osis}
            onChange={(event) => onOsisChange(event.target.value)}
            placeholder="John.1.1-5"
            style={{ width: "100%" }}
            ref={assignOsisRef}
          />
        </label>
      </div>

      {isBeginnerMode && (
        <p style={{ margin: 0, color: "#475569" }}>
          Simple mode shows only the essentials. Use the advanced panel when you need presets,
          saved searches, or guardrail filters.
        </p>
      )}

      {isAdvancedUi ? (
        <div>{advancedControls}</div>
      ) : (
        <details
          style={{
            border: "1px solid #cbd5f5",
            borderRadius: "0.75rem",
            padding: "0.75rem 1rem",
            background: "#f8fafc",
          }}
        >
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>Advanced</summary>
          <p style={{ margin: "0.75rem 0", fontSize: "0.9rem", color: "#475569" }}>
            Expand to tune presets, guardrail filters, and dataset facets. Saved search tools live
            here too.
          </p>
          {advancedControls}
        </details>
      )}

      <button type="submit" style={{ marginTop: "0.5rem" }} disabled={isSearching}>
        {isSearching ? "Searching." : "Search"}
      </button>
    </form>
  );
}
