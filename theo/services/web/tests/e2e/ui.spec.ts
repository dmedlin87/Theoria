import { expect, test, type APIRequestContext } from "@playwright/test";
import crypto from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const API_BASE = process.env.PLAYWRIGHT_API_BASE ?? "http://127.0.0.1:8000";

async function seedCorpus(request: APIRequestContext): Promise<void> {
  const content = `---
title: "Test Sermon"
authors:
  - "Jane Doe"
collection: "Gospels"
---

In the beginning was the Word (John 1:1-5), and the Word was with God.
Later we reflect on Genesis 1:1 in passing.
Test run: ${crypto.randomUUID()}
`;

  const response = await request.post(`${API_BASE}/ingest/file`, {
    multipart: {
      file: {
        name: "sermon.md",
        buffer: Buffer.from(content, "utf-8"),
        mimeType: "text/markdown",
      },
    },
  });
  expect(response.ok()).toBeTruthy();
}

test.beforeAll(async ({ request }) => {
  await seedCorpus(request);
});

test.describe("Theo Engine UI", () => {
  test("allows searching for ingested passages", async ({ page }) => {
    await page.goto("/search");

    await page.fill("input[name='q']", "Word");
    await page.click("button[type='submit']");
    const firstResultLink = page.getByRole("link", { name: /Open passage/i }).first();
    await expect(firstResultLink).toBeVisible();
  });

  test("filters verse mentions", async ({ page }) => {
    await page.goto("/verse/John.1.1");

    await expect(page.getByRole("heading", { name: /Verse Mentions/i })).toBeVisible();
    await expect(page.getByText(/Showing/)).toBeVisible();

    await page.fill("input[name='collection']", "Nonexistent");
    await page.click("button[type='submit']");
    await expect(page.getByText(/No mentions/, { exact: false })).toBeVisible();
  });

  test("navigates from search to document view", async ({ page }) => {
    await page.goto("/search");
    await page.fill("input[name='q']", "Word");
    await page.click("button[type='submit']");
    const firstResultLink = page.getByRole("link", { name: /Open passage/i }).first();
    await expect(firstResultLink).toBeVisible();

    await Promise.all([
      page.waitForNavigation(),
      firstResultLink.click(),
    ]);

    await expect(page.getByText(/Document ID:/)).toBeVisible();
    await expect(page.getByText(/In the beginning was the Word/)).toBeVisible();
  });

  test("uploads a new file", async ({ page }, testInfo) => {
    await page.goto("/upload");

    await mkdir(testInfo.outputDir, { recursive: true });
    const uploadPath = path.join(testInfo.outputDir, "upload.md");
    const uniqueContent = `Content mentioning Romans 8:1. Test run ${crypto.randomUUID()}`;
    await writeFile(uploadPath, uniqueContent, "utf-8");

    await page.setInputFiles("input[name='file']", uploadPath);
    await page.click("form[aria-label='Upload file'] button[type='submit']");

    await expect(page.getByRole("status")).toHaveText(/Upload complete/i);
  });
});
