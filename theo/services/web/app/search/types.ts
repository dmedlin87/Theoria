import type { components } from "../lib/generated/api";
import type { SortableDocumentGroup } from "./groupSorting";
import type { SearchFilters } from "./searchParams";

export type SearchResult = components["schemas"]["HybridSearchResult"];

export type SearchResponse = components["schemas"]["HybridSearchResponse"];

export type DocumentGroup = SortableDocumentGroup & {
  documentId: string;
  passages: SearchResult[];
};

export type SavedSearch = {
  id: string;
  name: string;
  filters: SearchFilters;
  createdAt: number;
};
