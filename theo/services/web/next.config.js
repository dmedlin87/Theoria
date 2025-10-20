import { createRequire } from "node:module";

/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    NEXT_PUBLIC_CASE_BUILDER_ENABLED:
      process.env.NEXT_PUBLIC_CASE_BUILDER_ENABLED ?? "false",
  },
};

let withBundleAnalyzer = (config) => config;

try {
  const require = createRequire(import.meta.url);
  withBundleAnalyzer = require("@next/bundle-analyzer")({
    enabled: process.env.ANALYZE === "true",
  });
} catch (error) {
  if (
    error &&
    error.code !== "MODULE_NOT_FOUND" &&
    error.code !== "ERR_MODULE_NOT_FOUND"
  ) {
    throw error;
  }
  console.warn("@next/bundle-analyzer not installed; skipping bundle analysis.");
}

export default withBundleAnalyzer(nextConfig);
