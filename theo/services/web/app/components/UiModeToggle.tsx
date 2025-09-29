"use client";

import { UiMode } from "../lib/useUiModePreference";

type UiModeToggleProps = {
  mode: UiMode;
  onChange: (mode: UiMode) => void;
};

export default function UiModeToggle({ mode, onChange }: UiModeToggleProps): JSX.Element {
  return (
    <fieldset
      style={{
        border: "1px solid #cbd5f5",
        borderRadius: "0.75rem",
        padding: "0.75rem 1rem",
        background: "#f8fafc",
        display: "grid",
        gap: "0.75rem",
      }}
    >
      <legend style={{ padding: "0 0.35rem", fontWeight: 600 }}>Workspace mode</legend>
      <div style={{ display: "flex", gap: "0.5rem" }}>
        {([
          { value: "simple", label: "Simple" },
          { value: "advanced", label: "Advanced" },
        ] as const).map((option) => {
          const isActive = option.value === mode;
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => onChange(option.value)}
              aria-pressed={isActive}
              style={{
                padding: "0.35rem 0.9rem",
                borderRadius: "999px",
                border: isActive ? "1px solid #2563eb" : "1px solid #cbd5f5",
                background: isActive ? "#2563eb" : "#ffffff",
                color: isActive ? "#ffffff" : "#1e293b",
                cursor: "pointer",
                fontWeight: 600,
              }}
            >
              {option.label}
            </button>
          );
        })}
      </div>
      <p style={{ margin: 0, fontSize: "0.85rem", color: "#475569" }}>
        Simple mode keeps only the core query fields visible. Switch to advanced when you need presets, facets, or
        workflow-specific controls.
      </p>
    </fieldset>
  );
}
