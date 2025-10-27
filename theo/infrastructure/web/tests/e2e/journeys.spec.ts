import { promises as fs } from "node:fs";

import { expect, test } from "./fixtures/error-guard";

const SEARCH_API_ROUTE = "**/api/search**";

test("@smoke home dashboard renders primary navigation", async ({ page }, testInfo) => {
  await page.goto("/");

  await expect(page.getByRole("link", { name: "Research" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Theoria");

  const artifactPath = testInfo.outputPath("home-state.json");
  await fs.writeFile(
    artifactPath,
    JSON.stringify({
      path: page.url(),
      navItems: await page
        .locator("nav a")
        .allInnerTexts(),
    })
  );
  await testInfo.attach("home-state", {
    path: artifactPath,
    contentType: "application/json",
  });

  const screenshot = await page.screenshot({ fullPage: true });
  await testInfo.attach("home-screenshot", {
    body: screenshot,
    contentType: "image/png",
  });
});

test("@full verse anchored search surfaces mocked results", async ({ page }, testInfo) => {
  const mockedResults = {
    results: [
      {
        id: "doc-osis",
        title: "Christology and OSIS references",
        osis_ref: "John.1.1",
        snippet: "In the beginning was the Word...",
      },
    ],
  };

  await page.route(SEARCH_API_ROUTE, async (route) => {
    await route.fulfill({
      status: 200,
      headers: { "content-type": "application/json" },
      body: JSON.stringify(mockedResults),
    });
  });

  await page.goto("/search");

  await page.fill("input[name='q']", "john prologue");
  await page.fill("input[name='osis']", "John.1.1");
  await page.click("button[type='submit']");

  await expect(page.getByText("Christology and OSIS references")).toBeVisible();
  await expect(page.getByText("In the beginning was the Word"))
    .toBeVisible();

  const artifactPath = testInfo.outputPath("search-results.json");
  await fs.writeFile(
    artifactPath,
    JSON.stringify({
      query: "john prologue",
      osis: "John.1.1",
      results: mockedResults.results,
    })
  );
  await testInfo.attach("search-results", {
    path: artifactPath,
    contentType: "application/json",
  });

  await page.unroute(SEARCH_API_ROUTE);
});
