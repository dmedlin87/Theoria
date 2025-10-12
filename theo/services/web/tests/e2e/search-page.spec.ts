import { expect, test } from "./fixtures/error-guard";

const SEARCH_API_ROUTE = "**/api/search**";

test.describe("Search page interactions", () => {
  test("@smoke shows a loading status while awaiting results", async ({ page }) => {
    let releaseSearch: () => void = () => {};
    const pending = new Promise<void>((resolve) => {
      releaseSearch = resolve;
    });

    await page.route(SEARCH_API_ROUTE, async (route) => {
      await pending;
      await route.fulfill({
        status: 200,
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ results: [] }),
      });
    });

    await page.goto("/search");
    await page.fill("input[name='q']", "integration test");
    await page.click("button[type='submit']");

    await expect(page.getByRole("status")).toHaveText("Searching.");

    releaseSearch();

    await expect(page.getByRole("status")).not.toBeVisible();
    await page.unroute(SEARCH_API_ROUTE);
  });
});
