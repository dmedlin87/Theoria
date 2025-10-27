"use client";

import type { CSSProperties, FormEvent } from "react";

import pageStyles from "./SearchPageClient.module.css";
import styles from "./SavedSearchControls.module.css";

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
      <form onSubmit={onSubmit} className={styles.form}>
        <label htmlFor="saved-search-name" style={visuallyHiddenStyle}>
          Saved search name
        </label>
        <input
          type="text"
          id="saved-search-name"
          value={savedSearchName}
          onChange={(event) => onSavedSearchNameChange(event.target.value)}
          placeholder="Name this search"
          className={pageStyles["search-saved-input"]}
        />
        <button type="submit" disabled={!savedSearchName.trim()}>
          Save current filters
        </button>
      </form>
      {savedSearches.length === 0 ? (
        <p className={pageStyles["search-saved-empty"]}>
          No saved searches yet. Configure filters and click save to store a preset.
        </p>
      ) : (
        <ul className={pageStyles["search-saved-list"]}>
          {savedSearches.map((saved) => {
            const formatted = formatFilters(saved.filters);
            return (
              <li key={saved.id} className={pageStyles["search-card"]}>
                <div className={pageStyles["search-card__header"]}>
                  <div className={pageStyles["search-card__info"]}>
                    <strong>{saved.name}</strong>
                    {formatted.description && (
                      <span className={pageStyles["search-card__description"]}>
                        {formatted.description}
                      </span>
                    )}
                  </div>
                  <div className={styles.actions}>
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
                  <div className={pageStyles["search-card__chips"]}>
                    {formatted.chips.map((chip) => (
                      <span key={chip.id} className={pageStyles["search-chip"]}>
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
