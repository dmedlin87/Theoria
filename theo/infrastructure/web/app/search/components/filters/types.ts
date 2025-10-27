import type { SearchFilters } from "../../searchParams";

export type SavedSearch = {
  id: string;
  name: string;
  filters: SearchFilters;
  createdAt: number;
};

export type SavedSearchFilterChip = {
  id: string;
  text: string;
};

export type FilterDisplay = {
  chips: SavedSearchFilterChip[];
  description: string;
};
