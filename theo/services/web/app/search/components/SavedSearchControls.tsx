"use client";

import type { FormEvent } from "react";

import type { SavedSearch } from "./SearchPageClient";
import type { SearchFilters } from "../searchParams";

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
      <form onSubmit={onSubmit} className="search-saved-form">
        <input
          type="text"
          value={savedSearchName}
          onChange={(event) => onSavedSearchNameChange(event.target.value)}
          placeholder="Name this search"
          className="search-saved-input"
        />
        <button type="submit" disabled={!savedSearchName.trim()}>
          Save current filters
        </button>
      </form>
      {savedSearches.length === 0 ? (
        <p className="search-saved-empty">
          No saved searches yet. Configure filters and click save to store a preset.
        </p>
      ) : (
        <ul className="search-saved-list">
          {savedSearches.map((saved) => {
            const formatted = formatFilters(saved.filters);
            return (
              <li key={saved.id} className="search-card">
                <div className="search-card__header">
                  <div className="search-card__info">
                    <strong>{saved.name}</strong>
                    {formatted.description && (
                      <span className="search-card__description">
                        {formatted.description}
                      </span>
                    )}
                  </div>
                  <div className="search-card__actions">
                    <button type="button" onClick={() => { void onApplySavedSearch(saved); }}>
                      Load preset
                    </button>
                    <button type="button" onClick={() => onDeleteSavedSearch(saved.id)}>
                      Delete
                    </button>
                  </div>
                </div>
                {formatted.chips.length > 0 && (
                  <div className="search-card__chips">
                    {formatted.chips.map((chip) => (
                      <span key={chip.id} className="search-chip">
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
