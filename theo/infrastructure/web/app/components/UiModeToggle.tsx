"use client";

import { UiMode } from "../lib/useUiModePreference";

type UiModeToggleProps = {
  mode: UiMode;
  onChange: (mode: UiMode) => void;
};

export default function UiModeToggle({ mode, onChange }: UiModeToggleProps): JSX.Element {
  return (
    <fieldset className="ui-mode-toggle">
      <legend className="ui-mode-toggle__legend">Workspace mode</legend>
      <div className="ui-mode-toggle__buttons">
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
              className={`ui-mode-toggle__button${isActive ? " ui-mode-toggle__button--active" : ""}`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
      <p className="ui-mode-toggle__description">
        Simple mode keeps only the core query fields visible. Switch to advanced when you need presets, facets, or
        workflow-specific controls.
      </p>
    </fieldset>
  );
}
