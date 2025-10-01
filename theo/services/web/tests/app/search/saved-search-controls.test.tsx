/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";

import { SavedSearchControls } from "../../../app/search/components/SavedSearchControls";
import type { SavedSearch } from "../../../app/search/components/SearchPageClient";
import type { SearchFilters } from "../../../app/search/searchParams";

const SAMPLE_FILTERS: SearchFilters = {
  query: "logos",
  osis: "",
  collection: "",
  author: "",
  sourceType: "",
  theologicalTradition: "",
  topicDomain: "",
  collectionFacets: [],
  datasetFacets: [],
  variantFacets: [],
  dateStart: "",
  dateEnd: "",
  includeVariants: false,
  includeDisputed: false,
  preset: "",
};

describe("SavedSearchControls", () => {
  it("renders saved searches with formatted chips", () => {
    const savedSearches: SavedSearch[] = [
      {
        id: "saved-1",
        name: "Logos study",
        filters: SAMPLE_FILTERS,
        createdAt: Date.now(),
      },
    ];
    const formatFilters = jest.fn().mockReturnValue({
      chips: [
        { id: "chip-1", text: "Query: logos" },
        { id: "chip-2", text: "Variants on" },
      ],
      description: "Includes variant readings",
    });
    const handleApply = jest.fn();
    const handleDelete = jest.fn();

    render(
      <SavedSearchControls
        savedSearchName=""
        onSavedSearchNameChange={() => {}}
        onSubmit={jest.fn()}
        savedSearches={savedSearches}
        onApplySavedSearch={handleApply}
        onDeleteSavedSearch={handleDelete}
        formatFilters={formatFilters}
      />,
    );

    expect(formatFilters).toHaveBeenCalledWith(SAMPLE_FILTERS);
    expect(screen.getByText("Logos study")).toBeInTheDocument();
    expect(screen.getByText("Includes variant readings")).toBeInTheDocument();
    expect(screen.getByText("Query: logos")).toBeInTheDocument();
    expect(screen.getByText("Variants on")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Load preset" }));
    expect(handleApply).toHaveBeenCalledWith(savedSearches[0]);

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(handleDelete).toHaveBeenCalledWith("saved-1");
  });

  it("shows an empty state when no saved searches exist", () => {
    render(
      <SavedSearchControls
        savedSearchName=""
        onSavedSearchNameChange={() => {}}
        onSubmit={jest.fn()}
        savedSearches={[]}
        onApplySavedSearch={jest.fn()}
        onDeleteSavedSearch={jest.fn()}
        formatFilters={() => ({ chips: [], description: "" })}
      />,
    );

    expect(
      screen.getByText("No saved searches yet. Configure filters and click save to store a preset."),
    ).toBeInTheDocument();
  });
});
