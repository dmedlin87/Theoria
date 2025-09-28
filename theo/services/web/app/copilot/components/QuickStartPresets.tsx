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
    <section
      style={{
        marginBottom: "1.5rem",
        padding: "1rem",
        background: "#f8fafc",
        borderRadius: "0.75rem",
        border: "1px solid #e2e8f0",
      }}
    >
      <h3 style={{ marginTop: 0, marginBottom: "0.5rem" }}>Quick start</h3>
      <p style={{ marginTop: 0, color: "#475569" }}>
        Use a preset prompt to auto-fill the form and run the workflow instantly.
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem" }}>
        {presets.map((preset) => (
          <button
            key={preset.id}
            type="button"
            onClick={() => onSelect(preset)}
            disabled={disabled}
            style={{
              flex: "1 1 240px",
              minWidth: 220,
              textAlign: "left",
              borderRadius: "0.75rem",
              padding: "0.75rem 1rem",
              border: "1px solid #cbd5f5",
              background: "#fff",
              cursor: disabled ? "not-allowed" : "pointer",
            }}
          >
            <strong style={{ display: "block", marginBottom: "0.25rem" }}>{preset.title}</strong>
            <span style={{ fontSize: "0.85rem", color: "#475569" }}>{preset.description}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
