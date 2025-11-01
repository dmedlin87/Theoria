import type { APIRequestContext } from "@playwright/test";
import { expect } from "@playwright/test";
import crypto from "node:crypto";

const API_BASE = process.env.PLAYWRIGHT_API_BASE ?? "http://127.0.0.1:8000";

export async function seedCorpus(request: APIRequestContext): Promise<void> {
  const content = `---\ntitle: "Test Sermon"\nauthors:\n  - "Jane Doe"\ncollection: "Gospels"\n---\n\nIn the beginning was the Word (John 1:1-5), and the Word was with God.\nLater we reflect on Genesis 1:1 in passing.\nTest run: ${crypto.randomUUID()}\n`;

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

export async function seedResearchNote(request: APIRequestContext): Promise<void> {
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
