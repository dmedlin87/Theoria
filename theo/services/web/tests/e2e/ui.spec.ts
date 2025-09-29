import { expect, test } from "./fixtures/error-guard";
import type { APIRequestContext, Page } from "@playwright/test";
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

async function seedResearchNote(request: APIRequestContext): Promise<void> {
  const payload = {
    osis: "John.1.1",
    body: "Playwright integration commentary on John 1:1",
    title: "Playwright commentary",
    stance: "apologetic",
    claim_type: "textual",
    confidence: 0.7,
    tags: ["playwright", "integration"],
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

test.describe("Theo Engine UI", () => {
  test("allows searching for ingested passages", async ({ page }) => {
    await page.goto("/search");

    await page.fill("input[name='q']", "Word");
    await page.click("button[type='submit']");
    const firstResultLink = page.getByRole("link", { name: /Open passage/i }).first();
    await expect(firstResultLink).toBeVisible();
  });

  test("primary navigation links load", async ({ page }) => {
    const navLinks: Array<{
      href: string;
      label: string;
      assertion: (page: Page) => Promise<void>;
    }> = [
      {
        href: "/chat",
        label: "Chat",
        assertion: async (pageInstance) => {
          await expect(pageInstance.getByRole("heading", { name: "Chat" })).toBeVisible();
        },
      },
      {
        href: "/search",
        label: "Search",
        assertion: async (pageInstance) => {
          await expect(pageInstance.getByRole("heading", { name: "Search" })).toBeVisible();
        },
      },
      {
        href: "/upload",
        label: "Upload",
        assertion: async (pageInstance) => {
          await expect(pageInstance.getByRole("heading", { name: "Upload" })).toBeVisible();
        },
      },
      {
        href: "/copilot",
        label: "Copilot",
        assertion: async (pageInstance) => {
          await expect(pageInstance.getByRole("heading", { name: "Copilot" })).toBeVisible();
        },
      },
      {
        href: "/verse/John.1.1",
        label: "Verse explorer",
        assertion: async (pageInstance) => {
          await expect(
            pageInstance.getByRole("heading", { name: /Verse Mentions/i })
          ).toBeVisible();
        },
      },
    ];

    for (const { href, label, assertion } of navLinks) {
      await page.goto("/");
      const navLink = page
        .getByRole("navigation", { name: "Primary" })
        .getByRole("link", { name: label, exact: true });
      await expect(navLink).toBeVisible();

      await Promise.all([
        page.waitForURL(`**${href}`, { waitUntil: "networkidle" }),
        navLink.click(),
      ]);

      await assertion(page);
    }
  });

  test("runs copilot workflows", async ({ page }) => {
    const observedWorkflows = new Set<string>();
    const observedExportPresets = new Set<string>();
    const baseCitation = {
      index: 0,
      osis: "John.1.1",
      anchor: "John 1:1",
      snippet: "In the beginning was the Word.",
      document_id: "doc-1",
      document_title: "Sample Document",
    };
    const ragAnswer = {
      summary: "Test summary",
      citations: [baseCitation],
    };

    await page.route("**/ai/*", async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname;
      if (path === "/ai/verse") {
        const payload = route.request().postDataJSON();
        expect(payload).toMatchObject({ osis: "John.1.1" });
        observedWorkflows.add("verse");
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            osis: payload.osis,
            question: payload.question,
            answer: ragAnswer,
            follow_ups: ["What parallels exist with Genesis 1?"],
          }),
        });
        return;
      }
      if (path === "/ai/sermon-prep" && !url.search) {
        const payload = route.request().postDataJSON();
        expect(payload.topic).toBe("Embodied hope");
        observedWorkflows.add("sermon");
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            topic: payload.topic,
            osis: payload.osis,
            outline: ["Point 1", "Point 2"],
            key_points: ["Key insight"],
            answer: ragAnswer,
          }),
        });
        return;
      }
      if (path === "/ai/comparative") {
        const payload = route.request().postDataJSON();
        expect(payload.participants).toEqual(["Origen", "Augustine"]);
        observedWorkflows.add("comparative");
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            osis: payload.osis,
            participants: payload.participants,
            comparisons: ["Origen emphasises pre-existence."],
            answer: ragAnswer,
          }),
        });
        return;
      }
      if (path === "/ai/multimedia") {
        const payload = route.request().postDataJSON();
        expect(payload.collection).toBe("Gospels");
        observedWorkflows.add("multimedia");
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            collection: payload.collection,
            highlights: ["Sample highlight from audio"],
            answer: ragAnswer,
          }),
        });
        return;
      }
      if (path === "/ai/devotional") {
        const payload = route.request().postDataJSON();
        expect(payload.focus).toBe("Logos");
        observedWorkflows.add("devotional");
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            osis: payload.osis,
            focus: payload.focus,
            reflection: "Reflect on the Word becoming flesh.",
            prayer: "Spirit, help me embody the Word.",
            answer: ragAnswer,
          }),
        });
        return;
      }
      if (path === "/ai/collaboration") {
        const payload = route.request().postDataJSON();
        expect(payload.viewpoints).toEqual(["Creation", "Logos"]);
        observedWorkflows.add("collaboration");
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            thread: payload.thread,
            synthesized_view: "Creation meets Logos in harmony.",
            answer: ragAnswer,
          }),
        });
        return;
      }
      if (path === "/ai/curation") {
        const payload = route.request().postDataJSON();
        expect(payload).toMatchObject({ since: "2024-01-01T00:00:00" });
        observedWorkflows.add("curation");
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            since: payload.since,
            documents_processed: 3,
            summaries: ["Sample Sermon — Gospels"],
          }),
        });
        return;
      }
      if (path === "/ai/sermon-prep/export") {
        const payload = route.request().postDataJSON();
        const format = new URL(route.request().url()).searchParams.get("format") ?? "markdown";
        expect(payload.topic).toBe("Embodied hope");
        observedExportPresets.add(`sermon-${format}`);
        await route.fulfill({
          status: 200,
          headers: {
            "content-type": format === "csv" ? "text/csv" : "text/plain",
            "content-disposition": `attachment; filename=sermon.${format}`,
          },
          body: `SERMON EXPORT (${format.toUpperCase()})`,
        });
        return;
      }
      if (path === "/ai/transcript/export") {
        const payload = route.request().postDataJSON();
        expect(payload.document_id).toBe("doc-123");
        observedExportPresets.add(`transcript-${payload.format}`);
        await route.fulfill({
          status: 200,
          headers: {
            "content-type": payload.format === "csv" ? "text/csv" : "text/plain",
            "content-disposition": `attachment; filename=transcript.${payload.format}`,
          },
          body: `TRANSCRIPT EXPORT (${String(payload.format).toUpperCase()})`,
        });
        return;
      }
      if (path === "/ai/citations/export") {
        const payload = route.request().postDataJSON();
        expect(Array.isArray(payload.citations)).toBeTruthy();
        expect(payload.citations).toHaveLength(1);
        const responseBody = {
          manifest: {
            export_id: "citations-1",
            schema_version: "2024-07-01",
            created_at: new Date().toISOString(),
            type: "documents",
            filters: {},
            totals: { documents: 1, passages: 1, returned: 1 },
            cursor: null,
            next_cursor: null,
            mode: null,
          },
          records: [
            {
              kind: "document",
              document_id: "doc-1",
              title: "Sample Document",
              collection: "Test",
              source_type: "article",
              authors: ["Jane Doe"],
              doi: "10.1234/example",
              venue: "Theo Journal",
              year: 2024,
              topics: ["Theology"],
              primary_topic: "Theology",
              enrichment_version: 1,
              provenance_score: 5,
              abstract: "Example abstract",
              source_url: "https://example.test",
              metadata: {},
              passages: [
                {
                  id: "passage-1",
                  document_id: "doc-1",
                  osis_ref: "John.1.1",
                  page_no: 1,
                  t_start: 0,
                  t_end: 5,
                  meta: { anchor: "John 1:1", snippet: "In the beginning" },
                },
              ],
            },
          ],
          csl: [
            {
              id: "doc-1",
              type: "article-journal",
              title: "Sample Document",
              author: [{ literal: "Jane Doe" }],
              note: "Anchors: John.1.1 (John 1:1)",
            },
          ],
          manager_payload: {
            format: "csl-json",
            export_id: "citations-1",
            zotero: { items: [{ id: "doc-1" }] },
            mendeley: { documents: [{ id: "doc-1" }] },
          },
        };
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(responseBody),
        });
        return;
      }
      await route.continue();
    });

    await page.goto("/copilot");
    await expect(page.getByRole("heading", { name: "Copilot" })).toBeVisible();

    await page.getByRole("button", { name: /^Verse brief/ }).click();
    await page.getByLabel("OSIS reference").fill("John.1.1");
    await page.getByLabel("Question").fill("How does the Logos reveal God's nature?");
    await Promise.all([
      page.waitForResponse((response) => response.url().endsWith("/ai/verse")),
      page.click("button[type='submit']"),
    ]);
    await expect(page.getByRole("heading", { name: /Verse brief for John\.1\.1/ })).toBeVisible();
    const exportButton = page.getByRole("button", { name: "Send to Zotero/Mendeley" });
    await expect(exportButton).toBeVisible();
    await Promise.all([
      page.waitForResponse((response) => response.url().endsWith("/ai/citations/export")),
      exportButton.click(),
    ]);
    await expect(
      page
        .getByRole("status")
        .filter({ hasText: /Downloaded CSL bibliography for the selected citations\./i })
    ).toBeVisible();

    await page.getByRole("button", { name: /^Sermon prep/ }).click();
    await page.getByLabel("Sermon topic").fill("Embodied hope");
    await page.getByLabel("OSIS anchor (optional)").fill("John.1.1");
    await Promise.all([
      page.waitForResponse((response) => response.url().endsWith("/ai/sermon-prep")),
      page.click("button[type='submit']"),
    ]);
    await expect(page.getByRole("heading", { name: /Sermon prep: Embodied hope/ })).toBeVisible();

    await page.getByRole("button", { name: /^Comparative analysis/ }).click();
    await page.getByLabel("OSIS reference").fill("John.1.1");
    await page.getByLabel("Participants \(comma separated\)").fill("Origen, Augustine");
    await Promise.all([
      page.waitForResponse((response) => response.url().endsWith("/ai/comparative")),
      page.click("button[type='submit']"),
    ]);
    await expect(page.getByRole("heading", { name: /Comparative analysis/ })).toBeVisible();

    await page.getByRole("button", { name: /^Multimedia digest/ }).click();
    await page.getByLabel("Collection \(optional\)").fill("Gospels");
    await Promise.all([
      page.waitForResponse((response) => response.url().endsWith("/ai/multimedia")),
      page.click("button[type='submit']"),
    ]);
    await expect(page.getByRole("heading", { name: "Multimedia digest" })).toBeVisible();

    await page.getByRole("button", { name: /^Devotional guide/ }).click();
    await page.getByLabel("OSIS reference").fill("John.1.1");
    await page.getByLabel("Focus theme").fill("Logos");
    await Promise.all([
      page.waitForResponse((response) => response.url().endsWith("/ai/devotional")),
      page.click("button[type='submit']"),
    ]);
    await expect(page.getByRole("heading", { name: /Devotional guide for John\.1\.1/ })).toBeVisible();

    await page.getByRole("button", { name: /^Collaboration reconciliation/ }).click();
    await page.getByLabel("Thread identifier").fill("forum-thread-1");
    await page.getByLabel("OSIS reference").fill("John.1.1");
    await page.getByLabel("Viewpoints \(comma separated\)").fill("Creation, Logos");
    await Promise.all([
      page.waitForResponse((response) => response.url().endsWith("/ai/collaboration")),
      page.click("button[type='submit']"),
    ]);
    await expect(page.getByRole("heading", { name: /Collaboration synthesis/ })).toBeVisible();

    await page.getByRole("button", { name: /^Corpus curation/ }).click();
    await page.getByLabel("Since \(ISO timestamp, optional\)").fill("2024-01-01T00:00:00");
    await Promise.all([
      page.waitForResponse((response) => response.url().endsWith("/ai/curation")),
      page.click("button[type='submit']"),
    ]);
    await expect(page.getByRole("heading", { name: "Corpus curation report" })).toBeVisible();

    await page.getByRole("button", { name: /^Export presets/ }).click();
    const presetSelect = page.getByLabel("Export preset");
    const exportPresets = [
      { id: "sermon-markdown", type: "sermon", urlSuffix: "/ai/sermon-prep/export?format=markdown" },
      { id: "sermon-ndjson", type: "sermon", urlSuffix: "/ai/sermon-prep/export?format=ndjson" },
      { id: "sermon-csv", type: "sermon", urlSuffix: "/ai/sermon-prep/export?format=csv" },
      { id: "sermon-pdf", type: "sermon", urlSuffix: "/ai/sermon-prep/export?format=pdf" },
      { id: "transcript-markdown", type: "transcript", urlSuffix: "/ai/transcript/export" },
      { id: "transcript-csv", type: "transcript", urlSuffix: "/ai/transcript/export" },
      { id: "transcript-pdf", type: "transcript", urlSuffix: "/ai/transcript/export" },
    ];

    for (const preset of exportPresets) {
      await presetSelect.selectOption(preset.id);
      if (preset.type === "sermon") {
        await page.getByLabel("Sermon topic").fill("Embodied hope");
        await page.getByLabel("OSIS anchor (optional)").fill("John.1.1");
      } else {
        await page.getByLabel("Document identifier").fill("doc-123");
      }
      await Promise.all([
        page.waitForResponse((response) => response.url().includes(preset.urlSuffix)),
        page.click("button[type='submit']"),
      ]);
      await expect(page.getByRole("heading", { name: /Export preset:/ })).toBeVisible();
    }

    expect(Array.from(observedWorkflows).sort()).toEqual(
      [
        "collaboration",
        "comparative",
        "curation",
        "devotional",
        "multimedia",
        "sermon",
        "verse",
      ].sort()
    );
    expect(Array.from(observedExportPresets).sort()).toEqual(
      [
        "sermon-pdf",
        "sermon-csv",
        "sermon-markdown",
        "sermon-ndjson",
        "transcript-pdf",
        "transcript-csv",
        "transcript-markdown",
      ].sort()
    );
  });

  test("filters verse mentions", async ({ page }) => {
    await page.goto("/verse/John.1.1");

    await expect(page.getByRole("heading", { name: /Verse Mentions/i })).toBeVisible();
    await expect(page.getByText(/Showing/)).toBeVisible();

    await page.fill("input[name='collection']", "Nonexistent");
    await page.click("button[type='submit']");
    await expect(page.getByText(/No mentions/, { exact: false })).toBeVisible();
  });

  test("renders research panels with data", async ({ page }) => {
    await page.goto("/verse/John.1.1");

    await expect(page.getByRole("heading", { name: "Research" })).toBeVisible();

    await expect(page.getByRole("heading", { name: "Cross-references" })).toBeVisible();
    await expect(page.getByText(/Genesis\.1\.1/)).toBeVisible();

    await expect(page.getByRole("heading", { name: "Textual variants" })).toBeVisible();
    await expect(page.getByText("English Standard Version")).toBeVisible();

    await expect(page.getByRole("heading", { name: "Morphology" })).toBeVisible();
    await expect(page.getByText(/Ἐν/, { exact: false })).toBeVisible();

    await expect(page.getByRole("heading", { name: "Commentaries & notes" })).toBeVisible();
    await expect(page.getByText(/Playwright commentary/)).toBeVisible();
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
