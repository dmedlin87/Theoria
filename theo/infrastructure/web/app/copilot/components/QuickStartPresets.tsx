import styles from "./QuickStartPresets.module.css";

import type { QuickStartPreset } from "./types";

type QuickStartPresetsProps = {
  presets: QuickStartPreset[];
  onSelect: (preset: QuickStartPreset) => void;
  disabled?: boolean;
};

export default function QuickStartPresets({
  presets,
  onSelect,
  disabled,
}: QuickStartPresetsProps): JSX.Element {
  return (
    <section className={styles.section}>
      <h3 className={styles.heading}>Quick start</h3>
      <p className={styles.description}>
        Use a preset prompt to auto-fill the form and run the workflow instantly.
      </p>
      <div className={styles.presetsGrid}>
        {presets.map((preset) => (
          <button
            key={preset.id}
            type="button"
            onClick={() => onSelect(preset)}
            disabled={disabled}
            className={styles.presetButton}
          >
            <strong className={styles.presetTitle}>{preset.title}</strong>
            <span className={styles.presetDescription}>{preset.description}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
