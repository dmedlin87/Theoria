"use client";

import { useState } from "react";

export type DeadSeaScrollLink = {
  id: string;
  fragment: string;
  scroll?: string | null;
  summary?: string | null;
  source?: string | null;
  url?: string | null;
};

interface DeadSeaScrollsChipProps {
  links: DeadSeaScrollLink[];
}

export function DeadSeaScrollsChip({ links }: DeadSeaScrollsChipProps) {
  const [expanded, setExpanded] = useState(false);

  const hasLinks = links.length > 0;
  const toggle = () => {
    if (!hasLinks) return;
    setExpanded((value) => !value);
  };

  return (
    <div style={{ display: "grid", gap: "0.75rem" }}>
      <button
        type="button"
        onClick={toggle}
        aria-expanded={expanded}
        disabled={!hasLinks}
        style={{
          alignSelf: "start",
          padding: "0.35rem 0.85rem",
          borderRadius: "999px",
          border: "1px solid var(--border, #e2e8f0)",
          background: hasLinks ? "#eef2ff" : "#f1f5f9",
          color: hasLinks ? "#312e81" : "#64748b",
          cursor: hasLinks ? "pointer" : "not-allowed",
          fontWeight: 600,
        }}
      >
        Dead Sea Scrolls {hasLinks ? `(${links.length})` : "— none"}
      </button>
      {expanded && hasLinks ? (
        <ul
          style={{
            listStyle: "none",
            padding: 0,
            margin: 0,
            display: "grid",
            gap: "0.75rem",
          }}
        >
          {links.map((link) => (
            <li
              key={link.id}
              style={{
                background: "#fff",
                borderRadius: "0.5rem",
                border: "1px solid var(--border, #e2e8f0)",
                padding: "0.75rem",
              }}
            >
              <div style={{ display: "grid", gap: "0.35rem" }}>
                <strong>{link.fragment}</strong>
                {link.scroll ? (
                  <span style={{ color: "var(--muted-foreground, #4b5563)" }}>
                    {link.scroll}
                  </span>
                ) : null}
                {link.summary ? <p style={{ margin: 0 }}>{link.summary}</p> : null}
                {link.source || link.url ? (
                  <span style={{ fontSize: "0.85rem", color: "#475569" }}>
                    {link.source ? `${link.source}` : ""}
                    {link.source && link.url ? " · " : ""}
                    {link.url ? (
                      <a href={link.url} target="_blank" rel="noreferrer">
                        View fragment
                      </a>
                    ) : null}
                  </span>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
