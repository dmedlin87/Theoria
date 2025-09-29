/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";

import DocumentClient from "../../../app/doc/[id]/DocumentClient";
import type { DocumentDetail } from "../../../app/doc/[id]/types";

function buildDocument(overrides: Partial<DocumentDetail> = {}): DocumentDetail {
  const now = new Date().toISOString();
  return {
    id: "doc-123",
    title: "Example Document",
    created_at: now,
    updated_at: now,
    passages: [],
    annotations: [],
    ...overrides,
  };
}

describe("DocumentClient source URL safety", () => {
  it("renders safe links for http URLs", () => {
    const document = buildDocument({ source_url: "https://example.com/original" });

    render(<DocumentClient initialDocument={document} />);

    const link = screen.getByRole("link", { name: "Original source" });
    expect(link).toHaveAttribute("href", "https://example.com/original");
  });

  it("renders unsafe schemes as plain text", () => {
    const document = buildDocument({ source_url: "javascript:alert(1)" });

    render(<DocumentClient initialDocument={document} />);

    expect(screen.queryByRole("link", { name: "Original source" })).not.toBeInTheDocument();
    expect(screen.getByText("Original source: javascript:alert(1)")).toBeInTheDocument();
  });

  it("renders structured annotations with linked passages", () => {
    const timestamp = new Date().toISOString();
    const document = buildDocument({
      passages: [
        {
          id: "passage-1",
          document_id: "doc-123",
          text: "Example passage",
          osis_ref: null,
          page_no: 4,
          t_start: null,
          t_end: null,
          meta: null,
        },
      ],
      annotations: [
        {
          id: "ann-1",
          document_id: "doc-123",
          type: "claim",
          body: "The speaker affirms the thesis.",
          stance: "supportive",
          passage_ids: ["passage-1"],
          group_id: "bundle-1",
          metadata: null,
          raw: null,
          legacy: false,
          created_at: timestamp,
          updated_at: timestamp,
        },
      ],
    });

    render(<DocumentClient initialDocument={document} />);

    expect(screen.getByText("Claim")).toBeInTheDocument();
    expect(screen.getByText("The speaker affirms the thesis.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Page 4/ })).toBeInTheDocument();
  });
});
