"use client";

import { useMemo, useState } from "react";

export type VariantReading = {
  id: string;
  osis: string;
  category: string;
  reading: string;
  note?: string | null;
  source?: string | null;
  witness?: string | null;
  translation?: string | null;
  confidence?: number | null;
};

function formatConfidence(value: number | null | undefined): string {
  if (typeof value !== "number") {
    return "—";
  }
  return `${Math.round(value * 100) / 100}`;
}

function readingLabel(reading: VariantReading, index: number): string {
  if (reading.witness) return reading.witness;
  if (reading.translation) return reading.translation;
  if (reading.source) return reading.source;
  return `Reading ${index + 1}`;
}

export function VariantCompareTable({ readings }: { readings: VariantReading[] }) {
  const defaultSelection = useMemo(
    () => readings.slice(0, Math.min(readings.length, 3)).map((item) => item.id),
    [readings],
  );
  const [selected, setSelected] = useState<string[]>(defaultSelection);

  const toggle = (id: string) => {
    setSelected((current) => {
      if (current.includes(id)) {
        if (current.length === 1) {
          return current;
        }
        return current.filter((item) => item !== id);
      }
      return [...current, id];
    });
  };

  const selectedReadings = readings.filter((reading) => selected.includes(reading.id));

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      <fieldset
        style={{
          margin: 0,
          padding: "0.75rem",
          borderRadius: "0.5rem",
          border: "1px solid var(--border, #e2e8f0)",
        }}
      >
        <legend style={{ padding: "0 0.35rem", fontWeight: 600 }}>Witness selection</legend>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem" }}>
          {readings.map((reading, index) => {
            const label = readingLabel(reading, index);
            return (
              <label key={reading.id} style={{ display: "inline-flex", gap: "0.35rem", alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={selected.includes(reading.id)}
                  onChange={() => toggle(reading.id)}
                />
                <span>{label}</span>
              </label>
            );
          })}
        </div>
      </fieldset>

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: "480px" }}>
          <thead>
            <tr>
              <th
                scope="col"
                style={{
                  textAlign: "left",
                  padding: "0.5rem",
                  borderBottom: "2px solid var(--border, #e2e8f0)",
                  width: "160px",
                }}
              >
                Attribute
              </th>
              {selectedReadings.map((reading, index) => (
                <th
                  key={reading.id}
                  scope="col"
                  style={{
                    textAlign: "left",
                    padding: "0.5rem",
                    borderBottom: "2px solid var(--border, #e2e8f0)",
                  }}
                >
                  {readingLabel(reading, index)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[
              {
                key: "category",
                label: "Category",
                render: (reading: VariantReading) => reading.category,
              },
              {
                key: "reading",
                label: "Reading",
                render: (reading: VariantReading) => reading.reading,
              },
              {
                key: "note",
                label: "Note",
                render: (reading: VariantReading) => reading.note ?? "—",
              },
              {
                key: "source",
                label: "Source",
                render: (reading: VariantReading) => reading.source ?? "—",
              },
              {
                key: "confidence",
                label: "Confidence",
                render: (reading: VariantReading) => formatConfidence(reading.confidence),
              },
            ].map((row) => (
              <tr key={row.key}>
                <th
                  scope="row"
                  style={{
                    textAlign: "left",
                    padding: "0.5rem",
                    borderBottom: "1px solid var(--border, #e2e8f0)",
                    verticalAlign: "top",
                  }}
                >
                  {row.label}
                </th>
                {selectedReadings.map((reading) => (
                  <td
                    key={`${row.key}-${reading.id}`}
                    style={{
                      padding: "0.5rem",
                      borderBottom: "1px solid var(--border, #e2e8f0)",
                      verticalAlign: "top",
                      whiteSpace: row.key === "reading" || row.key === "note" ? "normal" : "nowrap",
                    }}
                  >
                    {row.render(reading)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
