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
      <form onSubmit={onSubmit} style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
        <input
          type="text"
          value={savedSearchName}
          onChange={(event) => onSavedSearchNameChange(event.target.value)}
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
        <ul
          style={{
            listStyle: "none",
            padding: 0,
            margin: "0.75rem 0 0",
            display: "grid",
            gap: "0.5rem",
          }}
        >
          {savedSearches.map((saved) => {
            const formatted = formatFilters(saved.filters);
            return (
              <li
                key={saved.id}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.5rem",
                  padding: "0.75rem",
                  border: "1px solid #e2e8f0",
                  borderRadius: "0.75rem",
                  background: "#fff",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "grid", gap: "0.25rem" }}>
                    <strong>{saved.name}</strong>
                    {formatted.description && (
                      <span style={{ fontSize: "0.85rem", color: "#475569" }}>
                        {formatted.description}
                      </span>
                    )}
                  </div>
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    <button type="button" onClick={() => { void onApplySavedSearch(saved); }}>
                      Load preset
                    </button>
                    <button type="button" onClick={() => onDeleteSavedSearch(saved.id)}>
                      Delete
                    </button>
                  </div>
                </div>
                {formatted.chips.length > 0 && (
                  <div
                    style={{
                      display: "flex",
                      flexWrap: "wrap",
                      gap: "0.35rem",
                      marginTop: "0.35rem",
                    }}
                  >
                    {formatted.chips.map((chip) => (
                      <span
                        key={chip.id}
                        style={{
                          background: "#e2e8f0",
                          borderRadius: "999px",
                          color: "#1e293b",
                          display: "inline-flex",
                          fontSize: "0.75rem",
                          fontWeight: 500,
                          lineHeight: 1.2,
                          padding: "0.2rem 0.55rem",
                        }}
                      >
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
