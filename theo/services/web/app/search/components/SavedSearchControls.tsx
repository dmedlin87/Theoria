"use client";

import type { CSSProperties, FormEvent } from "react";

import styles from "./SearchPageClient.module.css";

import type { SavedSearch } from "./SearchPageClient";
import type { SearchFilters } from "../searchParams";
import type { SavedSearch } from "./filters/types";

const visuallyHiddenStyle: CSSProperties = {
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

type SavedSearchControlsProps = {
  savedSearchName: string;
  onSavedSearchNameChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  savedSearches: SavedSearch[];
  onApplySavedSearch: (saved: SavedSearch) => void | Promise<void>;
  onDeleteSavedSearch: (id: string) => void;
  formatFilters: (
    filters: SearchFilters,
  ) => {
    chips: { id: string; text: string }[];
    description: string;
  };
};

export function SavedSearchControls({
  savedSearchName,
  onSavedSearchNameChange,
  onSubmit,
  savedSearches,
  onApplySavedSearch,
  onDeleteSavedSearch,
  formatFilters,
}: SavedSearchControlsProps): JSX.Element {
  return (
    <>
      <form onSubmit={onSubmit} style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
        <label htmlFor="saved-search-name" style={visuallyHiddenStyle}>
          Saved search name
        </label>
        <input
          type="text"
          id="saved-search-name"
          value={savedSearchName}
          onChange={(event) => onSavedSearchNameChange(event.target.value)}
          placeholder="Name this search"
          className={styles["search-saved-input"]}
        />
        <button type="submit" disabled={!savedSearchName.trim()}>
          Save current filters
        </button>
      </form>
      {savedSearches.length === 0 ? (
        <p className={styles["search-saved-empty"]}>
          No saved searches yet. Configure filters and click save to store a preset.
        </p>
      ) : (
        <ul className={styles["search-saved-list"]}>
          {savedSearches.map((saved) => {
            const formatted = formatFilters(saved.filters);
            return (
              <li key={saved.id} className={styles["search-card"]}>
                <div className={styles["search-card__header"]}>
                  <div className={styles["search-card__info"]}>
                    <strong>{saved.name}</strong>
                    {formatted.description && (
                      <span className={styles["search-card__description"]}>
                        {formatted.description}
                      </span>
                    )}
                  </div>
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    <button
                      type="button"
                      onClick={() => {
                        void onApplySavedSearch(saved);
                      }}
                    >
                      Load preset
                    </button>
                    <button
                      type="button"
                      onClick={() => onDeleteSavedSearch(saved.id)}
                    >
                      Delete
                    </button>
                  </div>
                </div>
                {formatted.chips.length > 0 && (
                  <div className={styles["search-card__chips"]}>
                    {formatted.chips.map((chip) => (
                      <span key={chip.id} className={styles["search-chip"]}>
                        {chip.text}
                      </span>
                    ))}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
