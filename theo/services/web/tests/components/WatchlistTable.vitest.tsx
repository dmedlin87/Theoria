import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { useState } from "react";

import WatchlistTable from "../../app/admin/digests/components/WatchlistTable";
import type { WatchlistResponse } from "../../app/admin/digests/types";

describe("WatchlistTable", () => {
  const baseWatchlist: WatchlistResponse = {
    id: "watch-1",
    user_id: "user-1",
    name: "Scholar digest",
    cadence: "daily",
    delivery_channels: ["email"],
    filters: {
      topics: ["theology"],
      keywords: ["grace"],
      authors: ["Augustine"],
      osis: ["John.1"],
      metadata: null,
    },
    is_active: true,
    last_run: "2024-10-01T12:00:00Z",
    created_at: "2024-09-01T00:00:00Z",
    updated_at: "2024-10-01T12:00:00Z",
  };

  function renderTable(overrides?: Partial<WatchlistResponse>) {
    const handlers = {
      onEdit: vi.fn(),
      onSave: vi.fn(),
      onPreview: vi.fn(),
      onRun: vi.fn(),
      onDelete: vi.fn(),
      onViewEvents: vi.fn(),
      onToggleActiveOnly: vi.fn(),
      onPreviousPage: vi.fn(),
      onNextPage: vi.fn(),
    };

    function Harness() {
      const [watchlists, setWatchlists] = useState<WatchlistResponse[]>([{
        ...baseWatchlist,
        ...overrides,
      }]);

      return (
        <WatchlistTable
          watchlists={watchlists}
          totalCount={1}
          totalPages={1}
          page={0}
          showActiveOnly={false}
          onToggleActiveOnly={handlers.onToggleActiveOnly}
          onPreviousPage={handlers.onPreviousPage}
          onNextPage={handlers.onNextPage}
          loadedFor="user-1"
          onEdit={(id, updates) => {
            setWatchlists((current) =>
              current.map((watchlist) => {
                if (watchlist.id !== id) {
                  return watchlist;
                }

                const next: WatchlistResponse = {
                  ...watchlist,
                  ...updates,
                  filters: watchlist.filters,
                };

                if (updates.filters) {
                  next.filters = {
                    ...(watchlist.filters ?? {}),
                    ...updates.filters,
                  };
                }

                return next;
              }),
            );
            handlers.onEdit(id, updates);
          }}
          onSave={(watchlist) => handlers.onSave(watchlist)}
          onPreview={(id) => handlers.onPreview(id)}
          onRun={(id) => handlers.onRun(id)}
          onDelete={(id) => handlers.onDelete(id)}
          onViewEvents={(id) => handlers.onViewEvents(id)}
          formatDate={(value) => (value ? `formatted-${value}` : "never")}
          toCommaList={(values) => (values && values.length ? values.join(", ") : "")}
          fromCommaList={(value) =>
            value
              .split(/,/)
              .map((item) => item.trim())
              .filter(Boolean)
          }
        />
      );
    }

    render(<Harness />);

    return handlers;
  }

  it("allows inline editing and action triggers for administrators", async () => {
    const user = userEvent.setup();

    const handlers = renderTable();

    await user.click(screen.getByLabelText(/Show active only/i));
    expect(handlers.onToggleActiveOnly).toHaveBeenCalledWith(true);

    const row = screen.getAllByRole("row")[1];
    const withinRow = within(row);

    const cadenceSelect = withinRow.getByLabelText(/Cadence for Scholar digest/i);
    await user.selectOptions(cadenceSelect, "weekly");
    expect(handlers.onEdit).toHaveBeenLastCalledWith("watch-1", { cadence: "weekly" });
    handlers.onEdit.mockClear();

    const deliveryInput = withinRow.getByLabelText(/Delivery channels for Scholar digest/i);
    await user.clear(deliveryInput);
    fireEvent.change(deliveryInput, { target: { value: "email, sms" } });
    await waitFor(() =>
      expect(handlers.onEdit).toHaveBeenLastCalledWith("watch-1", { delivery_channels: ["email", "sms"] }),
    );
    await waitFor(() => expect(deliveryInput).toHaveValue("email, sms"));
    handlers.onEdit.mockClear();

    const topicInput = withinRow.getByLabelText(/Topics/i);
    await user.clear(topicInput);
    fireEvent.change(topicInput, { target: { value: "ethics, mission" } });
    await waitFor(() =>
      expect(handlers.onEdit).toHaveBeenLastCalledWith(
        "watch-1",
        expect.objectContaining({ filters: expect.objectContaining({ topics: ["ethics", "mission"] }) }),
      ),
    );
    handlers.onEdit.mockClear();

    await user.click(withinRow.getByRole("button", { name: /Save changes/i }));
    expect(handlers.onSave).toHaveBeenCalledWith(expect.objectContaining({ id: "watch-1" }));

    await user.click(withinRow.getByRole("button", { name: /Preview/i }));
    expect(handlers.onPreview).toHaveBeenCalledWith("watch-1");

    await user.click(withinRow.getByRole("button", { name: /Run now/i }));
    expect(handlers.onRun).toHaveBeenCalledWith("watch-1");

    await user.click(withinRow.getByRole("button", { name: /Delete/i }));
    expect(handlers.onDelete).toHaveBeenCalledWith("watch-1");

    await user.click(withinRow.getByRole("button", { name: /View events/i }));
    expect(handlers.onViewEvents).toHaveBeenCalledWith("watch-1");
  });
});
