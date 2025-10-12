import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    include: ["tests/**/*.vitest.{ts,tsx}"],
    environment: "jsdom",
    setupFiles: ["tests/vitest.setup.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      reportsDirectory: "coverage",
      include: [
        "app/components/**/*.{ts,tsx}",
        "app/search/hooks/useSearchFilters.ts",
      ],
      thresholds: {
        lines: 35,
        functions: 70,
        statements: 35,
        branches: 60,
      },
    },
  },
});
