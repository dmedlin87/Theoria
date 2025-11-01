import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import SearchResults from "../../app/search/components/SearchResults";
import type { DocumentGroup } from "../../app/search/components/SearchPageClient";

vi.mock("../../app/components/VirtualList", () => ({
  __esModule: true,
  default: ({
    items,
    renderItem,
    containerProps,
  }: {
    items: DocumentGroup[];
    renderItem: (item: DocumentGroup, index: number) => ReactNode;
    containerProps?: Record<string, unknown>;
  }) => (
    <div data-testid="virtual-list" {...containerProps}>
      {items.map((item, index) => (
        <div key={item.documentId}>{renderItem(item, index)}</div>
      ))}
    </div>
  ),
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ children, onClick, ...props }: AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a
      {...props}
      onClick={(event) => {
        event.preventDefault();
        onClick?.(event);
      }}
    >
      {children}
    </a>
  ),
}));

describe("SearchResults", () => {
  it("renders an informative empty state when no groups are available", () => {
    render(<SearchResults groups={[]} queryTokens={[]} onPassageClick={vi.fn()} />);

    expect(screen.getByText(/No results found/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Try adjusting your search query or filters/i),
    ).toBeInTheDocument();
  });

  it("highlights query tokens and forwards passage click telemetry", async () => {
    const user = userEvent.setup();
    const handlePassageClick = vi.fn();
    const groups: DocumentGroup[] = [
      {
        documentId: "doc-1",
        title: "John 1 Study",
        rank: 1,
        score: 0.92,
        passages: [
          {
            id: "passage-1",
            document_id: "doc-1",
            document_rank: 1,
            document_score: 0.92,
            score: 0.9,
            osis_ref: "John 1:1",
            page_no: 2,
            t_start: null,
            t_end: null,
            text: "In the beginning was the Word, echoing Genesis 1.",
            rank: 2,
          },
        ],
      },
    ];

    render(
      <SearchResults
        groups={groups}
        queryTokens={["Word", "Genesis"]}
        onPassageClick={handlePassageClick}
      />,
    );

    const highlights = screen.getAllByText(/Word|Genesis/, { selector: "mark" });
    expect(highlights).toHaveLength(2);
    expect(highlights[0]).toHaveTextContent("Word");

    await user.click(screen.getByRole("link", { name: /Open document/i }));

    expect(handlePassageClick).toHaveBeenCalledWith({
      id: "passage-1",
      document_id: "doc-1",
      rank: 2,
    });
  });
});
