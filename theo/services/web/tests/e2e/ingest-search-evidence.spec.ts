import { expect, test } from "./fixtures/error-guard";
import type { Page } from "@playwright/test";

import { seedCorpus, seedResearchNote } from "./helpers/seeding";

async function openSearch(page: Page): Promise<void> {
  await page.goto("/search");
  await expect(page.getByRole("heading", { name: "Search" })).toBeVisible();
}

test.describe("Ingest → search → evidence flow", () => {
  test.beforeAll(async ({ request }) => {
    await seedCorpus(request);
    await seedResearchNote(request);
  });

  test("@smoke indexes ingested content and surfaces passages in search", async ({ page }) => {
    await openSearch(page);

    await page.fill("input[name='q']", "Word");
    await page.click("button[type='submit']");

    const firstResultLink = page.getByRole("link", { name: /Open passage/i }).first();
    await expect(firstResultLink).toBeVisible();
    await expect(page.getByText(/In the beginning was the Word/i)).toBeVisible();
  });

  test("@full opens document evidence and exports a transcript digest", async ({ page }) => {
    await openSearch(page);

    await page.fill("input[name='q']", "Word");
    await page.click("button[type='submit']");

    const firstResultLink = page.getByRole("link", { name: /Open passage/i }).first();
    await expect(firstResultLink).toBeVisible();

    await Promise.all([
      page.waitForURL("**/doc/**"),
      firstResultLink.click(),
    ]);

    await expect(page.getByRole("heading", { level: 2, name: "Test Sermon" })).toBeVisible();
    await expect(page.getByText("Document ID:")).toContainText("Document ID:");

    await page.route("**/export/deliverable", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          export_id: "digest-1",
          status: "completed",
          manifest: {
            export_id: "digest-1",
            schema_version: "2024-07-01",
            generated_at: new Date().toISOString(),
            type: "transcript",
          },
          assets: [
            {
              format: "markdown",
              filename: "transcript-digest.md",
              media_type: "text/markdown",
              storage_path: "/exports/transcript-digest.md",
            },
          ],
          message: "Transcript export ready.",
        }),
      });
    });

    const exportButton = page.getByRole("button", { name: "Export Q&A digest" });
    await Promise.all([
      page.waitForResponse((response) => response.url().includes("/export/deliverable") && response.request().method() === "POST"),
      exportButton.click(),
    ]);

    await expect(
      page
        .getByRole("status")
        .filter({ hasText: /Transcript export ready\./i })
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Download transcript-digest.md" })).toBeVisible();
  });
});
