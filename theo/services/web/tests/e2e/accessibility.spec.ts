import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./fixtures/error-guard";

const ROUTES: Array<{ path: string; landmark: { role: string; name: string | RegExp } }> = [
  { path: "/", landmark: { role: "heading", name: /Chat/i } },
  { path: "/search", landmark: { role: "heading", name: /Search/i } },
  { path: "/upload", landmark: { role: "heading", name: /Upload/i } },
  { path: "/copilot", landmark: { role: "heading", name: /Copilot/i } },
  { path: "/verse/John.1.1", landmark: { role: "heading", name: /Verse mentions/i } },
];

test.describe("accessibility checks", () => {
  for (const { path, landmark } of ROUTES) {
    test(`@smoke has no critical axe violations on ${path}`, async ({ page }) => {
      await page.goto(path);
      await expect(page.getByRole(landmark.role as never, { name: landmark.name })).toBeVisible();

      const accessibilityScanResults = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa"])
        .analyze();

      expect(accessibilityScanResults.violations).toEqual([]);
    });
  }
});
