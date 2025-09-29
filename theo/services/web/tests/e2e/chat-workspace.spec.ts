import { expect, test } from "./fixtures/error-guard";

const STREAMING_BODY =
  JSON.stringify({ type: "answer_fragment", content: "The Logos motif recalls Genesis 1." }) +
  "\n" +
  JSON.stringify({
    type: "complete",
    response: {
      sessionId: "playwright-session",
      answer: {
        summary: "The Logos motif recalls Genesis 1.",
        citations: [
          {
            index: 0,
            osis: "John.1.1",
            anchor: "John 1:1",
            passage_id: "passage-1",
            document_id: "doc-1",
            document_title: "Test Commentary",
            snippet: "In the beginning was the Word, and the Word was with God.",
            source_url: null,
          },
        ],
        model_name: null,
        model_output: null,
        guardrail_profile: null,
      },
    },
  });

test.describe("Chat workspace", () => {
  test("shows a loading state before the response resolves", async ({ page }) => {
    await page.route("**/ai/workflows/chat", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 600));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: "slow-session",
          answer: { summary: "Patience rewarded.", citations: [] },
        }),
      });
    });

    await page.goto("/chat");
    await page.fill("textarea[name='question']", "How does patience shape study?");
    await page.click("button[type='submit']");

    await expect(page.getByText("Generating response…")).toBeVisible();
    await expect(page.getByText("Patience rewarded.")).toBeVisible();
  });

  test("streams chat answers with citations", async ({ page }) => {
    await page.route("**/ai/workflows/chat", async (route) => {
      await route.fulfill({
        status: 200,
        headers: { "content-type": "application/x-ndjson" },
        body: STREAMING_BODY,
      });
    });

    await page.goto("/chat");
    await page.fill("textarea[name='question']", "Explain John 1:1");
    await page.click("button[type='submit']");

    await expect(page.getByText("The Logos motif recalls Genesis 1.")).toBeVisible();
    await expect(page.getByRole("link", { name: "Open John 1:1" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Search references" })).toBeVisible();
  });

  test("renders guardrail violations", async ({ page }) => {
    await page.route("**/ai/workflows/chat", async (route) => {
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({
          type: "guardrail_violation",
          message: "Request blocked by safeguards.",
          trace_id: "guard-99",
          suggestions: [
            {
              action: "search",
              label: "Search related passages",
              description: "Inspect related passages in the search workspace.",
              query: "List conspiracies",
            },
          ],
          metadata: {
            code: "test_guardrail",
            guardrail: "retrieval",
            suggested_action: "search",
            filters: null,
            safe_refusal: false,
            reason: "Playwright stub",
          },
        }),
      });
    });

    await page.goto("/chat");
    await page.fill("textarea[name='question']", "List conspiracies");
    await page.click("button[type='submit']");

    await expect(page.getByText("Request blocked by safeguards.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Rephrase question" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Search related passages" })).toBeVisible();
  });

  test("suggests recovery actions for invalid chat requests", async ({ page }) => {
    await page.route("**/ai/workflows/chat", async (route) => {
      await route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({ detail: "messages cannot be empty" }),
      });
    });

    await page.goto("/chat");
    await page.fill("textarea[name='question']", "Why was the request invalid?");
    await page.click("button[type='submit']");

    await expect(page.getByText("messages cannot be empty")).toBeVisible();
    await expect(page.getByRole("button", { name: "Search related passages" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Upload supporting documents" })).toBeVisible();
  });
});
