import React from "react";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterAll, afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SystemHealthCard } from "../../../app/dashboard/components/SystemHealthCard";

const fetchSpy = vi.spyOn(globalThis, "fetch");

function jsonResponse(body: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

describe("SystemHealthCard", () => {
  beforeEach(() => {
    fetchSpy.mockReset();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllTimers();
  });

  afterAll(() => {
    fetchSpy.mockRestore();
  });

  it("renders adapter details from the health endpoint", async () => {
    fetchSpy.mockResolvedValue(
      jsonResponse({
        status: "healthy",
        message: "All systems operational.",
        checked_at: "2025-01-01T00:00:00Z",
        adapters: [
          {
            name: "database",
            status: "healthy",
            message: "Database reachable",
            latency_ms: 12.3,
          },
          {
            name: "redis",
            status: "unavailable",
            message: "Redis unreachable",
            latency_ms: null,
          },
        ],
      }),
    );

    render(<SystemHealthCard />);

    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());

    const [request] = fetchSpy.mock.calls[0] ?? [];
    if (request instanceof Request) {
      expect(request.url).toContain("/health/detail");
    } else {
      expect(request).toContain("/health/detail");
    }

    expect(await screen.findByText(/System health/i)).toBeInTheDocument();
    expect(screen.getByText("Database reachable")).toBeInTheDocument();
    expect(screen.getByText("Redis unreachable")).toBeInTheDocument();
    expect(screen.getByText(/Response time 12.3 ms/)).toBeInTheDocument();
  });

  it("shows an error when the request fails", async () => {
    fetchSpy.mockResolvedValue(new Response("Upstream failure", { status: 503 }));

    render(<SystemHealthCard />);

    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());

    expect(await screen.findByText("Upstream failure")).toBeInTheDocument();
    expect(screen.getByText(/Unavailable/)).toBeInTheDocument();
  });
});
