import { expect, test } from "./fixtures/error-guard";

test.describe("Watchlist review workflow", () => {
  test("@smoke surfaces topic digest context and preview results", async ({ page }) => {
    const digestPayload = {
      generated_at: new Date("2024-12-01T12:00:00Z").toISOString(),
      window_start: new Date("2024-11-24T12:00:00Z").toISOString(),
      topics: [
        {
          topic: "Johannine theology",
          new_documents: 2,
          total_documents: 8,
          document_ids: ["doc-john-prologue"],
        },
      ],
    };
    const watchlists = [
      {
        id: "watch-1",
        user_id: "owner-123",
        name: "Resurrection alerts",
        filters: { topics: ["resurrection"], keywords: ["hope"], authors: null, osis: null, metadata: null },
        cadence: "weekly",
        delivery_channels: ["email"],
        is_active: true,
        last_run: new Date("2024-11-30T09:00:00Z").toISOString(),
        created_at: new Date("2024-10-01T09:00:00Z").toISOString(),
        updated_at: new Date("2024-11-30T09:00:00Z").toISOString(),
      },
    ];
    const previewResponse = {
      id: null,
      watchlist_id: "watch-1",
      run_started: new Date("2024-12-01T10:00:00Z").toISOString(),
      run_completed: new Date("2024-12-01T10:05:00Z").toISOString(),
      window_start: new Date("2024-11-24T10:00:00Z").toISOString(),
      matches: [
        {
          document_id: "doc-hope",
          passage_id: "passage-1",
          osis: "John.11.25",
          snippet: "I am the resurrection and the life.",
          reasons: ["keyword: hope"],
        },
      ],
      document_ids: ["doc-hope"],
      passage_ids: ["passage-1"],
      delivery_status: "preview",
      error: null,
    };

    await page.route("**/ai/digest", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(digestPayload) });
        return;
      }
      await route.continue();
    });

    await page.route("**/ai/digest/watchlists?user_id=owner-123", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(watchlists) });
    });

    await page.route("**/ai/digest/watchlists/watch-1/preview", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(previewResponse) });
    });

    await page.goto("/admin/digests");

    await expect(page.getByRole("heading", { name: "Topic digests" })).toBeVisible();
    await expect(page.getByText(/Johannine theology/)).toBeVisible();

    await page.getByLabel("User ID").fill("owner-123");
    await Promise.all([
      page.waitForResponse((response) => response.url().includes("/ai/digest/watchlists?user_id=owner-123")),
      page.getByRole("button", { name: "Load watchlists" }).click(),
    ]);

    await expect(page.getByRole("row", { name: /Resurrection alerts/ })).toBeVisible();

    await Promise.all([
      page.waitForResponse((response) =>
        response.url().includes("/ai/digest/watchlists/watch-1/preview") && response.request().method() === "GET"
      ),
      page.getByRole("button", { name: "Preview" }).click(),
    ]);

    await expect(page.getByRole("heading", { name: "Most recent result" })).toBeVisible();
    await expect(page.getByText(/Preview completed at/)).toContainText("matches");
    await page.getByText("View matches").click();
    await expect(page.getByText("doc-hope")).toBeVisible();
  });

  test("@full runs watchlists and inspects recent events", async ({ page }) => {
    const digestPayload = {
      generated_at: new Date("2024-12-01T12:00:00Z").toISOString(),
      window_start: new Date("2024-11-24T12:00:00Z").toISOString(),
      topics: [],
    };
    const watchlists = [
      {
        id: "watch-1",
        user_id: "owner-123",
        name: "Resurrection alerts",
        filters: { topics: ["resurrection"], keywords: ["hope"], authors: null, osis: null, metadata: null },
        cadence: "weekly",
        delivery_channels: ["email"],
        is_active: true,
        last_run: new Date("2024-11-30T09:00:00Z").toISOString(),
        created_at: new Date("2024-10-01T09:00:00Z").toISOString(),
        updated_at: new Date("2024-11-30T09:00:00Z").toISOString(),
      },
    ];
    const runResponse = {
      id: "run-1",
      watchlist_id: "watch-1",
      run_started: new Date("2024-12-01T10:10:00Z").toISOString(),
      run_completed: new Date("2024-12-01T10:12:00Z").toISOString(),
      window_start: new Date("2024-11-24T10:00:00Z").toISOString(),
      matches: [
        {
          document_id: "doc-hope",
          passage_id: "passage-2",
          osis: "1Cor.15.20",
          snippet: "Christ has been raised from the dead.",
          reasons: ["topic: resurrection"],
        },
      ],
      document_ids: ["doc-hope"],
      passage_ids: ["passage-2"],
      delivery_status: "delivered",
      error: null,
    };
    const eventsResponse = [
      {
        id: "run-0",
        watchlist_id: "watch-1",
        run_started: new Date("2024-11-30T08:00:00Z").toISOString(),
        run_completed: new Date("2024-11-30T08:03:00Z").toISOString(),
        window_start: new Date("2024-11-23T08:00:00Z").toISOString(),
        matches: [],
        document_ids: [],
        passage_ids: [],
        delivery_status: "queued",
        error: null,
      },
    ];

    await page.route("**/ai/digest", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(digestPayload) });
        return;
      }
      if (route.request().method() === "POST") {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(digestPayload) });
        return;
      }
      await route.continue();
    });

    await page.route("**/ai/digest/watchlists?user_id=owner-123", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(watchlists) });
    });

    await page.route("**/ai/digest/watchlists/watch-1/preview", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(runResponse) });
    });

    await page.route("**/ai/digest/watchlists/watch-1/run", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(runResponse) });
    });

    await page.route("**/ai/digest/watchlists/watch-1/events", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(eventsResponse) });
    });

    await page.goto("/admin/digests");
    await page.getByLabel("User ID").fill("owner-123");
    await Promise.all([
      page.waitForResponse((response) => response.url().includes("/ai/digest/watchlists?user_id=owner-123")),
      page.getByRole("button", { name: "Load watchlists" }).click(),
    ]);

    await Promise.all([
      page.waitForResponse((response) =>
        response.url().includes("/ai/digest/watchlists/watch-1/run") && response.request().method() === "POST"
      ),
      page.getByRole("button", { name: "Run now" }).click(),
    ]);

    await expect(page.getByText(/Run completed at/)).toBeVisible();

    const sinceInput = page.getByLabel("Since timestamp (ISO)");
    await sinceInput.fill("2024-11-01T00:00:00Z");

    await Promise.all([
      page.waitForResponse((response) => response.url().includes("/ai/digest/watchlists/watch-1/events")),
      page.getByRole("button", { name: "View events" }).click(),
    ]);

    await expect(page.getByText("Showing 1 events for watchlist watch-1.")).toBeVisible();
    await expect(page.getByText(/queued/i)).toBeVisible();
  });
});
