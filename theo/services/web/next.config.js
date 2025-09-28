/** @type {import('next').NextConfig} */
const nextConfig = {};

let withBundleAnalyzer = (config) => config;

try {
  withBundleAnalyzer = require("@next/bundle-analyzer")({
    enabled: process.env.ANALYZE === "true",
  });
} catch (error) {
  if (error && error.code !== "MODULE_NOT_FOUND") {
    throw error;
  }
  console.warn("@next/bundle-analyzer not installed; skipping bundle analysis.");
}

module.exports = withBundleAnalyzer(nextConfig);
