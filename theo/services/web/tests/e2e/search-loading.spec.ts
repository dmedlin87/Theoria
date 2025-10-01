import { expect, test, type APIRequestContext } from "@playwright/test";
import crypto from "node:crypto";

const API_BASE = process.env.PLAYWRIGHT_API_BASE ?? "http://127.0.0.1:8000";

async function seedCorpus(request: APIRequestContext): Promise<void> {
  const content = `---
  title: "Search Fixture"
  authors:
    - "Test User"
  collection: "Gospels"
---

  In the beginning was the Word (John 1:1-5).
  Test run: ${crypto.randomUUID()}
  `;

  const response = await request.post(`${API_BASE}/ingest/file`, {
    multipart: {
      file: {
        name: "fixture.md",
        buffer: Buffer.from(content, "utf-8"),
        mimeType: "text/markdown",
      },
    },
  });
  expect(response.ok()).toBeTruthy();
}

async function seedResearchNote(request: APIRequestContext): Promise<void> {
  const payload = {
    osis: "John.1.1",
    body: "Playwright commentary",
    title: "Playwright commentary",
    stance: "apologetic",
    claim_type: "textual",
    confidence: 0.7,
    tags: ["playwright"],
    evidences: [
      {
        source_type: "crossref",
        source_ref: "Genesis.1.1",
        snippet: "Creation language links the passages.",
        osis_refs: ["Genesis.1.1"],
      },
    ],
  };

  const response = await request.post(`${API_BASE}/research/notes`, {
    data: JSON.stringify(payload),
    headers: { "content-type": "application/json" },
  });
  expect(response.ok()).toBeTruthy();
}

test.beforeAll(async ({ request }) => {
  await seedCorpus(request);
  await seedResearchNote(request);
});

test("renders server search results for initial queries", async ({ page }) => {
  await page.goto("/search?q=Word");

  const firstResultLink = page.getByRole("link", { name: /Open passage/i }).first();
  await expect(firstResultLink).toBeVisible();
});

test("shows loading state while executing a search", async ({ page }) => {
  await page.route("**/api/search**", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 250));
    await route.fulfill({
      status: 200,
      headers: { "content-type": "application/json", "x-reranker": "playwright" },
      body: JSON.stringify({
        results: [
          {
            id: "playwright-result",
            document_id: "doc-playwright",
            snippet: "Playwright snippet",
            document_title: "Playwright Test Document",
            document_rank: 1,
            document_score: 0.5,
            score: 0.5,
          },
        ],
      }),
    });
  });

  await page.goto("/search");
  await page.fill("input[name='q']", "playwright");
  await page.click("button[type='submit']");

  const loadingMessage = page.getByRole("status");
  await expect(loadingMessage).toHaveText("Searching.");

  const firstResultLink = page.getByRole("link", { name: /Open passage/i }).first();
  await expect(firstResultLink).toBeVisible();
  await expect(page.getByText(/Reranked by playwright/i)).toBeVisible();
});
