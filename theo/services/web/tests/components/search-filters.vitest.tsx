import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import SearchFilters from "../../app/search/components/SearchFilters";

describe("SearchFilters", () => {
  afterEach(() => {
    cleanup();
  });

  const baseProps = {
    query: "",
    osis: "",
    collection: "",
    author: "",
    sourceType: "",
    theologicalTradition: "",
    topicDomain: "",
  };

  it("invokes change handlers for every control", async () => {
    const user = userEvent.setup();
    const onQueryChange = vi.fn();
    const onOsisChange = vi.fn();
    const onCollectionChange = vi.fn();
    const onAuthorChange = vi.fn();
    const onSourceTypeChange = vi.fn();
    const onTraditionChange = vi.fn();
    const onDomainChange = vi.fn();
    const onReset = vi.fn();

    render(
      <SearchFilters
        {...baseProps}
        onQueryChange={onQueryChange}
        onOsisChange={onOsisChange}
        onCollectionChange={onCollectionChange}
        onAuthorChange={onAuthorChange}
        onSourceTypeChange={onSourceTypeChange}
        onTheologicalTraditionChange={onTraditionChange}
        onTopicDomainChange={onDomainChange}
        onReset={onReset}
      />
    );

    fireEvent.change(screen.getByLabelText(/search query/i, { selector: "input" }), {
      target: { value: "lexical" },
    });
    fireEvent.change(screen.getByLabelText(/osis reference/i, { selector: "input" }), {
      target: { value: "John.1.1" },
    });
    fireEvent.change(screen.getByLabelText(/collection/i, { selector: "input" }), {
      target: { value: "Sermons" },
    });
    fireEvent.change(screen.getByLabelText(/author/i, { selector: "input" }), {
      target: { value: "Augustine" },
    });
    fireEvent.change(screen.getByLabelText(/source type/i, { selector: "select" }), {
      target: { value: "pdf" },
    });
    fireEvent.change(screen.getByLabelText(/theological tradition/i, { selector: "select" }), {
      target: { value: "baptist" },
    });
    fireEvent.change(screen.getByLabelText(/topic domain/i, { selector: "select" }), {
      target: { value: "christology" },
    });

    await user.click(screen.getByRole("button", { name: /clear all/i }));

    expect(onQueryChange).toHaveBeenLastCalledWith("lexical");
    expect(onOsisChange).toHaveBeenLastCalledWith("John.1.1");
    expect(onCollectionChange).toHaveBeenLastCalledWith("Sermons");
    expect(onAuthorChange).toHaveBeenLastCalledWith("Augustine");
    expect(onSourceTypeChange).toHaveBeenLastCalledWith("pdf");
    expect(onTraditionChange).toHaveBeenLastCalledWith("baptist");
    expect(onDomainChange).toHaveBeenLastCalledWith("christology");
    expect(onReset).toHaveBeenCalledTimes(1);
  });

  it("omits the reset button when no handler is supplied", () => {
    render(
      <SearchFilters
        {...baseProps}
        onQueryChange={vi.fn()}
        onOsisChange={vi.fn()}
        onCollectionChange={vi.fn()}
        onAuthorChange={vi.fn()}
        onSourceTypeChange={vi.fn()}
        onTheologicalTraditionChange={vi.fn()}
        onTopicDomainChange={vi.fn()}
      />
    );

    expect(screen.queryByRole("button", { name: /clear all/i })).toBeNull();
  });
});
