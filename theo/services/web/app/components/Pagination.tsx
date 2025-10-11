"use client";

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  className?: string;
}

export default function Pagination({
  currentPage,
  totalPages,
  onPageChange,
  className = "",
}: PaginationProps): JSX.Element {
  if (totalPages <= 1) {
    return <></>;
  }

  const pages: (number | "ellipsis")[] = [];
  
  // Always show first page
  pages.push(1);

  // Calculate range around current page
  const rangeStart = Math.max(2, currentPage - 1);
  const rangeEnd = Math.min(totalPages - 1, currentPage + 1);

  // Add ellipsis after first page if needed
  if (rangeStart > 2) {
    pages.push("ellipsis");
  }

  // Add pages around current
  for (let i = rangeStart; i <= rangeEnd; i++) {
    pages.push(i);
  }

  // Add ellipsis before last page if needed
  if (rangeEnd < totalPages - 1) {
    pages.push("ellipsis");
  }

  // Always show last page if there's more than one page
  if (totalPages > 1) {
    pages.push(totalPages);
  }

  return (
    <nav
      role="navigation"
      aria-label="Pagination"
      className={`pagination ${className}`.trim()}
    >
      <div className="cluster-sm" style={{ justifyContent: "center" }}>
        <button
          type="button"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
          className="btn btn-secondary btn-sm"
          aria-label="Previous page"
        >
          ← Previous
        </button>

        {pages.map((page, index) => {
          if (page === "ellipsis") {
            return (
              <span
                key={`ellipsis-${index}`}
                className="pagination-ellipsis"
                aria-hidden="true"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  padding: "0 0.5rem",
                  color: "var(--color-text-muted)",
                }}
              >
                …
              </span>
            );
          }

          const isActive = page === currentPage;
          return (
            <button
              key={page}
              type="button"
              onClick={() => onPageChange(page)}
              disabled={isActive}
              className={isActive ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm"}
              aria-label={`Page ${page}`}
              aria-current={isActive ? "page" : undefined}
              style={{ minWidth: "2.5rem" }}
            >
              {page}
            </button>
          );
        })}

        <button
          type="button"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          className="btn btn-secondary btn-sm"
          aria-label="Next page"
        >
          Next →
        </button>
      </div>
    </nav>
  );
}
