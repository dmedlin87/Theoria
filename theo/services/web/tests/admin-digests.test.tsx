/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import DigestDashboard from "../app/admin/digests/DigestDashboard";

describe("DigestDashboard", () => {
  const baseUrl = "http://127.0.0.1:8000";

  beforeEach(() => {
    jest.resetAllMocks();
    process.env.NEXT_PUBLIC_API_BASE_URL = baseUrl;
    global.fetch = jest.fn();
  });

  function okJson(data: unknown) {
    return {
      ok: true,
      json: async () => data,
      text: async () => JSON.stringify(data),
    } as Response;
  }

  it("renders digest data and allows refreshing", async () => {
    const initialDigest = {
      generated_at: "2024-03-01T10:00:00Z",
      window_start: "2024-02-25T00:00:00Z",
      topics: [
        {
          topic: "Pauline theology",
          summary: "Letters emphasising grace",
          new_documents: 2,
          total_documents: 10,
          document_ids: ["doc-1", "doc-2"],
        },
      ],
    };
    const refreshedDigest = {
      ...initialDigest,
      generated_at: "2024-03-02T12:00:00Z",
      topics: [
        {
          topic: "Messianic hope",
          summary: "New material on prophetic promises",
          new_documents: 3,
          total_documents: 8,
          document_ids: ["doc-9"],
        },
      ],
    };

    let digestCalls = 0;
    (global.fetch as jest.Mock).mockImplementation((input: RequestInfo, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.url;
      if (url === `${baseUrl}/ai/digest` && (!init || !init.method || init.method === "GET")) {
        digestCalls += 1;
        return Promise.resolve(okJson(digestCalls > 1 ? refreshedDigest : initialDigest));
      }
      if (url.startsWith(`${baseUrl}/ai/digest?hours=`) && init?.method === "POST") {
        return Promise.resolve(okJson(refreshedDigest));
      }
      if (url.includes("/watchlists")) {
        return Promise.resolve(okJson([]));
      }
      throw new Error(`Unhandled request: ${url}`);
    });

    render(<DigestDashboard />);

    expect(global.fetch).toHaveBeenCalledWith(`${baseUrl}/ai/digest`, expect.any(Object));

    await waitFor(() => {
      expect(screen.getByText("Pauline theology")).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /refresh digest/i }));
    });

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        `${baseUrl}/ai/digest?hours=168`,
        expect.objectContaining({ method: "POST" }),
      );
    });

    await waitFor(() => {
      expect(screen.getByText("Messianic hope")).toBeInTheDocument();
    });
  });

  it("loads watchlists, updates settings, and triggers runs", async () => {
    const digestPayload = {
      generated_at: "2024-03-01T10:00:00Z",
      window_start: "2024-02-25T00:00:00Z",
      topics: [],
    };
    const watchlist = {
      id: "watch-1",
      user_id: "admin",
      name: "Initial name",
      filters: { topics: ["Christology"], keywords: ["incarnation"], authors: [] },
      cadence: "daily",
      delivery_channels: ["in_app"],
      is_active: true,
      last_run: "2024-02-28T09:00:00Z",
      created_at: "2024-02-01T00:00:00Z",
      updated_at: "2024-02-02T00:00:00Z",
    };
    const updatedWatchlist = { ...watchlist, name: "Updated name" };
    const runResult = {
      id: "run-1",
      watchlist_id: "watch-1",
      run_started: "2024-03-01T08:00:00Z",
      run_completed: "2024-03-01T08:00:30Z",
      window_start: "2024-02-28T08:00:00Z",
      matches: [
        {
          document_id: "doc-1",
          passage_id: null,
          osis: "John.1.1",
          snippet: "In the beginning was the Word",
          reasons: ["topic match"],
        },
      ],
      document_ids: ["doc-1"],
      passage_ids: [],
      delivery_status: "preview",
      error: null,
    };
    const eventsPayload = [
      {
        ...runResult,
        id: "run-previous",
        run_started: "2024-02-28T08:00:00Z",
        run_completed: "2024-02-28T08:00:30Z",
        delivery_status: "delivered",
      },
    ];

    (global.fetch as jest.Mock).mockImplementation((input: RequestInfo, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.url;
      const method = init?.method ?? "GET";
      if (url === `${baseUrl}/ai/digest` && method === "GET") {
        return Promise.resolve(okJson(digestPayload));
      }
      if (url.startsWith(`${baseUrl}/ai/digest/watchlists?`) && method === "GET") {
        return Promise.resolve(okJson([watchlist]));
      }
      if (url === `${baseUrl}/ai/digest/watchlists/${watchlist.id}` && method === "PATCH") {
        expect(init?.body).toBe(JSON.stringify({ name: "Updated name" }));
        return Promise.resolve(okJson(updatedWatchlist));
      }
      if (url === `${baseUrl}/ai/digest/watchlists/${watchlist.id}/run` && method === "POST") {
        return Promise.resolve(okJson(runResult));
      }
      if (url === `${baseUrl}/ai/digest/watchlists/${watchlist.id}/events` && method === "GET") {
        return Promise.resolve(okJson(eventsPayload));
      }
      return Promise.resolve(okJson([]));
    });

    render(<DigestDashboard />);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(`${baseUrl}/ai/digest`, expect.any(Object));
    });

    fireEvent.change(screen.getByLabelText(/user id/i), { target: { value: "admin" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /load watchlists/i }));
    });

    await waitFor(() => {
      expect(screen.getByDisplayValue("Initial name")).toBeInTheDocument();
    });

    const nameInput = screen.getByDisplayValue("Initial name");
    fireEvent.change(nameInput, { target: { value: "Updated name" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save changes/i }));
    });

    await waitFor(() => {
      expect(screen.getByDisplayValue("Updated name")).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /run now/i }));
    });

    await waitFor(() => {
      expect(screen.getByText(/Run completed/i)).toBeInTheDocument();
      expect(screen.getByText(/John.1.1/)).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /view events/i }));
    });

    await waitFor(() => {
      expect(screen.getByText(/Showing 1 events/)).toBeInTheDocument();
      expect(screen.getByText(/delivered/)).toBeInTheDocument();
    });
  });

  it("creates a watchlist for the selected user", async () => {
    const digestPayload = {
      generated_at: "2024-03-01T10:00:00Z",
      window_start: "2024-02-25T00:00:00Z",
      topics: [],
    };
    const createdWatchlist = {
      id: "watch-create",
      user_id: "analyst-1",
      name: "Daily prophets",
      filters: { topics: ["Prophecy"], keywords: [], authors: [] },
      cadence: "daily",
      delivery_channels: ["in_app"],
      is_active: true,
      last_run: null,
      created_at: "2024-03-01T00:00:00Z",
      updated_at: "2024-03-01T00:00:00Z",
    };

    (global.fetch as jest.Mock).mockImplementation((input: RequestInfo, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.url;
      const method = init?.method ?? "GET";
      if (url === `${baseUrl}/ai/digest` && method === "GET") {
        return Promise.resolve(okJson(digestPayload));
      }
      if (url.startsWith(`${baseUrl}/ai/digest/watchlists?`) && method === "GET") {
        return Promise.resolve(okJson([]));
      }
      if (url === `${baseUrl}/ai/digest/watchlists` && method === "POST") {
        expect(init?.body).toBe(
          JSON.stringify({
            user_id: "analyst-1",
            name: "Daily prophets",
            cadence: "daily",
            delivery_channels: ["in_app"],
            filters: { topics: ["Prophecy"], keywords: null, authors: null },
          }),
        );
        return Promise.resolve(okJson(createdWatchlist));
      }
      return Promise.resolve(okJson([]));
    });

    render(<DigestDashboard />);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(`${baseUrl}/ai/digest`, expect.any(Object));
    });

    fireEvent.change(screen.getByLabelText(/user id/i), { target: { value: "analyst-1" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /load watchlists/i }));
    });

    const creationFormHeading = screen.getByRole("heading", { level: 3, name: /create watchlist/i });
    const creationForm = creationFormHeading.closest("form");
    expect(creationForm).not.toBeNull();
    const creation = within(creationForm as HTMLFormElement);
    fireEvent.change(creation.getByLabelText(/^name$/i), { target: { value: "Daily prophets" } });
    fireEvent.change(creation.getByLabelText(/topics/i), { target: { value: "Prophecy" } });

    await act(async () => {
      fireEvent.click(creation.getByRole("button", { name: /create watchlist/i }));
    });

    await waitFor(() => {
      expect(screen.getByDisplayValue("Daily prophets")).toBeInTheDocument();
    });
  });
});
