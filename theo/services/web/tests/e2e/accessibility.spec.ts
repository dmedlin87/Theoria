import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "@playwright/test";

const ROUTES = ["/", "/verse/John.3.16", "/copilot"];

test.describe("@a11y axe smoke", () => {
  for (const route of ROUTES) {
    test(`axe scan for ${route}`, async ({ page }) => {
      await page.goto(route, { waitUntil: "networkidle" });
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa"])
        .analyze();
      const criticalViolations = results.violations.filter(
        (violation) => violation.impact === "critical"
      );

      if (criticalViolations.length > 0) {
        test.info().attachments.push({
          name: `axe-${route}-critical.json`,
          body: JSON.stringify(criticalViolations, null, 2),
          contentType: "application/json",
        });
      }

      expect(criticalViolations, `Critical accessibility issues detected on ${route}`).toHaveLength(0);
    });
  }
});
