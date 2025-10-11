import { expect, test } from "./fixtures/error-guard";

const GRAPH_RESPONSE = {
  osis: "John.3.16",
  nodes: [
    { id: "verse:John.3.16", label: "John 3:16", kind: "verse", osis: "John.3.16", data: null },
    {
      id: "mention:passage-1",
      label: "Example Document",
      kind: "mention",
      osis: null,
      data: {
        document_id: "doc-1",
        passage_id: "passage-1",
        page_no: 3,
        t_start: 12,
        t_end: 20,
        document_title: "Example Document",
        source_type: "pdf",
        collection: "Sermons",
        authors: ["Alice"],
      },
    },
    { id: "verse:Matthew.5.44", label: "Matthew 5:44", kind: "verse", osis: "Matthew.5.44", data: null },
    { id: "verse:Luke.6.27", label: "Luke 6:27", kind: "verse", osis: "Luke.6.27", data: null },
  ],
  edges: [
    {
      id: "mention:passage-1",
      source: "verse:John.3.16",
      target: "mention:passage-1",
      kind: "mention",
      summary: "For God so loved the world",
      perspective: null,
      tags: null,
      weight: null,
      source_type: "pdf",
      collection: "Sermons",
      authors: ["Alice"],
      seed_id: null,
      related_osis: null,
      source_label: "Example Document",
    },
    {
      id: "contradiction:seed-1:Matthew.5.44",
      source: "verse:John.3.16",
      target: "verse:Matthew.5.44",
      kind: "contradiction",
      summary: "Tension summary",
      perspective: "skeptical",
      tags: ["tension"],
      weight: 1,
      source_type: null,
      collection: null,
      authors: null,
      seed_id: "seed-1",
      related_osis: "Matthew.5.44",
      source_label: "Skeptic Digest",
    },
    {
      id: "harmony:seed-2:Luke.6.27",
      source: "verse:John.3.16",
      target: "verse:Luke.6.27",
      kind: "harmony",
      summary: "Harmony summary",
      perspective: "apologetic",
      tags: ["unity"],
      weight: 0.5,
      source_type: null,
      collection: null,
      authors: null,
      seed_id: "seed-2",
      related_osis: "Luke.6.27",
      source_label: "Harmony Source",
    },
  ],
  filters: {
    perspectives: ["apologetic", "skeptical"],
    source_types: ["pdf"],
  },
};

const MENTIONS_RESPONSE = {
  osis: "John.3.16",
  total: 1,
  mentions: [
    {
      context_snippet: "For God so loved the world",
      passage: {
        id: "passage-1",
        document_id: "doc-1",
        text: "For God so loved the world",
        osis_ref: "John.3.16",
        page_no: 3,
        t_start: 12,
        t_end: 20,
        meta: {
          document_title: "Example Document",
          source_type: "pdf",
          collection: "Sermons",
          authors: ["Alice"],
        },
      },
    },
  ],
};

const OVERVIEW_RESPONSE = {
  osis: "John.3.16",
  mode: "apologetic",
  consensus: [],
  disputed: [],
  manuscripts: [],
};

test.describe("Verse relationship graph", () => {
  test("renders network and supports filtering", async ({ page }) => {
    await page.route("**/features/discovery", async (route) => {
      await route.fulfill({
        status: 200,
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ features: { verse_timeline: false } }),
      });
    });

    await page.route("**/research/overview**", async (route) => {
      await route.fulfill({
        status: 200,
        headers: { "content-type": "application/json" },
        body: JSON.stringify(OVERVIEW_RESPONSE),
      });
    });

    await page.route("**/verses/John.3.16/mentions**", async (route) => {
      await route.fulfill({
        status: 200,
        headers: { "content-type": "application/json" },
        body: JSON.stringify(MENTIONS_RESPONSE),
      });
    });

    await page.route("**/verses/John.3.16/graph**", async (route) => {
      await route.fulfill({
        status: 200,
        headers: { "content-type": "application/json" },
        body: JSON.stringify(GRAPH_RESPONSE),
      });
    });

    await page.goto("/verse/John.3.16");

    await expect(page.getByTestId("verse-graph")).toBeVisible();
    await expect(page.getByTestId("verse-graph-summary")).toHaveText(
      /Showing 3 of 3 relationships\./,
    );

    const skepticalToggle = page.getByLabel("Skeptical");
    await skepticalToggle.click();
    await expect(page.getByTestId("verse-graph-summary")).toHaveText(
      /Showing 2 of 3 relationships\./,
    );

    const pdfToggle = page.getByLabel("PDF");
    await pdfToggle.click();
    await expect(page.getByTestId("verse-graph-summary")).toHaveText(
      /Showing 1 of 3 relationships\./,
    );

    const mentionLink = page.getByTestId("graph-node-link-mention:passage-1");
    await expect(mentionLink).toHaveAttribute("href", /doc-1/);
  });
});
