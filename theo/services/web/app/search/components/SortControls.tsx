"use client";

import { ChangeEvent } from "react";
import styles from "./SortControls.module.css";

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
      className={styles.fieldset}
    >
      <legend className={styles.legend}>Sort results</legend>
      <div className={styles.optionsContainer}>
        {SORT_OPTIONS.map((option) => {
          const isActive = value === option.key;
          return (
            <label
              key={option.key}
              className={`${styles.optionLabel} ${isActive ? styles.active : ""}`}
            >
              <input
                type="radio"
                name="sort"
                value={option.key}
                checked={isActive}
                onChange={handleChange}
                className={styles.radioInput}
                aria-describedby={`sort-${option.key}-description`}
              />
              <span>
                <span className={styles.optionTitle}>{option.label}</span>
                <span
                  id={`sort-${option.key}-description`}
                  className={styles.optionDescription}
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
