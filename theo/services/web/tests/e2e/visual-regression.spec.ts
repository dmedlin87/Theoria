import { test, expect } from "@playwright/test";
import percySnapshot from "@percy/playwright";

test.describe("@visual visual regression", () => {
  test("search page states", async ({ page }) => {
    await page.goto("/search", { waitUntil: "networkidle" });
    await percySnapshot(page, "Search Page - Empty");

    await page.fill("input[name='q']", "logos");
    await page.click("button[type='submit']");
    await page.waitForLoadState("networkidle");

    await expect(page.getByRole("main")).toBeVisible();
    await percySnapshot(page, "Search Page - Results");
  });
});
