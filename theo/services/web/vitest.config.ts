import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/**/*.vitest.{ts,tsx}"],
    environment: "jsdom",
    setupFiles: ["tests/vitest.setup.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      reportsDirectory: "coverage",
      thresholds: {
        statements: 82,
        lines: 82,
        functions: 80,
        branches: 75,
        perFile: true,
      },
      all: true,
      include: ["app/**/*.{ts,tsx}", "components/**/*.{ts,tsx}", "lib/**/*.{ts,tsx}"],
      exclude: ["tests/**"],
    },
  },
});
