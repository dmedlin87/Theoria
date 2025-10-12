/**
 * Skeleton loading state for search results
 * Provides visual feedback during search operations
 */
export function SearchSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="skeleton-search-results" aria-busy="true" aria-label="Loading search results">
      {Array.from({ length: count }, (_, index) => (
        <div key={index} className="skeleton-result-group">
          <div className="skeleton skeleton-result-title" />
          <div className="skeleton skeleton-result-meta" />
          <div className="skeleton skeleton-passage" />
          <div className="skeleton skeleton-passage" />
        </div>
      ))}
    </div>
  );
}
