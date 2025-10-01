"use client";

import type { FormEvent } from "react";

import type { SearchFilters } from "../searchParams";
import type { SavedSearch } from "../types";
import {
  SAVED_SEARCH_CHIP_CONTAINER_STYLE,
  SAVED_SEARCH_CHIP_STYLE,
} from "./SearchPageClient";

type SavedSearchesPanelProps = {
  savedSearches: SavedSearch[];
  savedSearchName: string;
  onNameChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onApply: (saved: SavedSearch) => void | Promise<void>;
  onDelete: (id: string) => void;
  formatFilters: (filters: SearchFilters) => {
    chips: { id: string; text: string }[];
    description: string;
  };
};

export default function SavedSearchesPanel({
  savedSearches,
  savedSearchName,
  onNameChange,
  onSubmit,
  onApply,
  onDelete,
  formatFilters,
}: SavedSearchesPanelProps): JSX.Element {
  return (
    <section aria-label="Saved searches" style={{ display: "grid", gap: "0.75rem" }}>
      <form onSubmit={onSubmit} style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
        <input
          type="text"
          value={savedSearchName}
          onChange={(event) => onNameChange(event.target.value)}
          placeholder="Name this search"
          style={{ flex: "1 1 220px", minWidth: "200px" }}
        />
        <button type="submit" disabled={!savedSearchName.trim()}>
          Save current filters
        </button>
      </form>

      {savedSearches.length === 0 ? (
        <p style={{ margin: 0, fontSize: "0.9rem", color: "#555" }}>
          No saved searches yet. Configure filters and click save to store a preset.
        </p>
      ) : (
        <ul
          style={{
            listStyle: "none",
            padding: 0,
            margin: 0,
            display: "grid",
            gap: "0.75rem",
          }}
        >
          {savedSearches.map((saved) => {
            const { chips } = formatFilters(saved.filters);
            return (
              <li
                key={saved.id}
                style={{
                  display: "grid",
                  gap: "0.5rem",
                  border: "1px solid #e2e8f0",
                  borderRadius: "0.5rem",
                  padding: "0.75rem 1rem",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem" }}>
                  <div>
                    <strong>{saved.name}</strong>
                    <p style={{ margin: "0.25rem 0 0", fontSize: "0.85rem", color: "#555" }}>
                      Saved on {new Date(saved.createdAt).toLocaleString()}
                    </p>
                  </div>
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button type="button" onClick={() => void onApply(saved)}>
                      Run
                    </button>
                    <button type="button" onClick={() => onDelete(saved.id)}>
                      Delete
                    </button>
                  </div>
                </div>
                {chips.length > 0 && (
                  <div style={SAVED_SEARCH_CHIP_CONTAINER_STYLE}>
                    {chips.map((chip) => (
                      <span key={chip.id} style={SAVED_SEARCH_CHIP_STYLE}>
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
    </section>
  );
}
