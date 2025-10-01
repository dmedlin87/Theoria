"use client";

import { ChangeEvent } from "react";

import { GroupSortKey } from "../groupSorting";

export const SORT_OPTIONS: { key: GroupSortKey; label: string; description: string }[] = [
  {
    key: "rank",
    label: "Rank",
    description: "Prioritize editorial rank when available.",
  },
  {
    key: "score",
    label: "Score",
    description: "Sort by highest document score first.",
  },
  {
    key: "title",
    label: "Title",
    description: "Order alphabetically by document title.",
  },
];

export type SortControlsProps = {
  value: GroupSortKey;
  onChange: (key: GroupSortKey) => void;
};

export function SortControls({ value, onChange }: SortControlsProps): JSX.Element {
  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    onChange(event.target.value as GroupSortKey);
  };

  return (
    <fieldset
      role="radiogroup"
      aria-label="Sort search results"
      style={{
        border: "1px solid #d1d5db",
        borderRadius: "0.75rem",
        padding: "0.75rem 1rem",
        display: "grid",
        gap: "0.5rem",
      }}
    >
      <legend style={{ fontWeight: 600, padding: "0 0.5rem" }}>Sort results</legend>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
        {SORT_OPTIONS.map((option) => {
          const isActive = value === option.key;
          return (
            <label
              key={option.key}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.5rem",
                padding: "0.5rem 0.75rem",
                borderRadius: "999px",
                border: isActive ? "2px solid #1d4ed8" : "1px solid #d1d5db",
                background: isActive ? "#dbeafe" : "#f9fafb",
                cursor: "pointer",
                transition: "all 0.2s ease-in-out",
              }}
            >
              <input
                type="radio"
                name="sort"
                value={option.key}
                checked={isActive}
                onChange={handleChange}
                style={{ margin: 0 }}
                aria-describedby={`sort-${option.key}-description`}
              />
              <span>
                <span style={{ display: "block", fontWeight: 600 }}>{option.label}</span>
                <span
                  id={`sort-${option.key}-description`}
                  style={{ display: "block", fontSize: "0.8rem", color: "#4b5563" }}
                >
                  {option.description}
                </span>
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
