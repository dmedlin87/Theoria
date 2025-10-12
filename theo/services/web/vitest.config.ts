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
      include: ["app/chat/useSessionRestoration.ts"],
      thresholds: {
        lines: 80,
        functions: 80,
        statements: 80,
        branches: 80,
      },
      all: true,
      include: ["app/**/*.{ts,tsx}", "components/**/*.{ts,tsx}", "lib/**/*.{ts,tsx}"],
      exclude: ["tests/**"],
    },
  },
});
