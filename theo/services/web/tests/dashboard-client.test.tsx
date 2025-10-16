/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

import { DashboardClient } from "../app/dashboard/DashboardClient";
import type { DashboardSummary } from "../app/dashboard/types";

describe("DashboardClient", () => {
  const baseUrl = "http://127.0.0.1:8000";

  beforeEach(() => {
    process.env.NEXT_PUBLIC_API_BASE_URL = baseUrl;
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  it("renders metrics and activity from initial data", () => {
    const summary: DashboardSummary = {
      generated_at: new Date().toISOString(),
      user: { name: "Dr. Luther", plan: "Scholar", timezone: "UTC", last_login: null },
      metrics: [
        {
          id: "documents",
          label: "Documents indexed",
          value: 42,
          unit: null,
          delta_percentage: 12.5,
          trend: "up",
        },
      ],
      activity: [
        {
          id: "activity-1",
          type: "document_ingested",
          title: "Uploaded Institutes",
          description: "Systematic theology",
          occurred_at: new Date().toISOString(),
          href: "/doc/1",
        },
      ],
      quick_actions: [
        { id: "search", label: "Search", href: "/search", description: "Explore", icon: "🔍" },
      ],
    };

    render(<DashboardClient initialData={summary} />);

    expect(screen.getByText(/Your personalised research console/i)).toBeInTheDocument();
    expect(screen.getByText("Documents indexed")).toBeInTheDocument();
    expect(screen.getByText("Uploaded Institutes")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /refresh data/i })).toBeInTheDocument();
  });

  it("shows loading state while fetching initial data", async () => {
    let resolveFetch: (value: Response) => void;
    (global.fetch as jest.Mock).mockImplementation(
      () =>
        new Promise<Response>((resolve) => {
          resolveFetch = resolve;
        }),
    );

    render(<DashboardClient initialData={null} />);

    expect(screen.getByText(/Refreshing dashboard/i)).toBeInTheDocument();
    expect(screen.getByText(/Loading activity/i)).toBeInTheDocument();

    const payload: DashboardSummary = {
      generated_at: new Date().toISOString(),
      user: { name: "Researcher", plan: null, timezone: null, last_login: null },
      metrics: [],
      activity: [],
      quick_actions: [],
    };

    await act(async () => {
      resolveFetch!(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });

    await waitFor(() => {
      expect(screen.queryByText(/Refreshing dashboard/i)).not.toBeInTheDocument();
    });
  });

  it("surfaces an error when the dashboard request fails", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      new Response("Server error", { status: 500, statusText: "Internal Server Error" }),
    );

    render(<DashboardClient initialData={null} />);

    await waitFor(() => {
      expect(screen.getByText(/Unable to refresh dashboard/i)).toBeInTheDocument();
    });

    (global.fetch as jest.Mock).mockResolvedValue(
      new Response(JSON.stringify({
        generated_at: new Date().toISOString(),
        user: { name: "Researcher", plan: null, timezone: null, last_login: null },
        metrics: [],
        activity: [],
        quick_actions: [],
      }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /try again/i }));
    });

    await waitFor(() => {
      expect(screen.queryByText(/Unable to refresh dashboard/i)).not.toBeInTheDocument();
    });
  });
});
