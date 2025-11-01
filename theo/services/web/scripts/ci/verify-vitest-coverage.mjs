#!/usr/bin/env node
import { readFile } from "node:fs/promises";
import path from "node:path";

const COVERAGE_DIR = process.env.VITEST_COVERAGE_DIR ?? "coverage";
const THRESHOLDS = {
  lines: 80,
  statements: 80,
  functions: 80,
  branches: 80,
};

const summaryPath = path.join(COVERAGE_DIR, "coverage-summary.json");

async function loadSummary() {
  try {
    const raw = await readFile(summaryPath, "utf8");
    return JSON.parse(raw);
  } catch (error) {
    console.error(`Unable to read Vitest coverage summary at ${summaryPath}:`, error);
    process.exitCode = 1;
    throw error;
  }
}

function toPercent(metric) {
  if (typeof metric?.pct === "number") {
    return metric.pct;
  }
  if (typeof metric?.covered === "number" && typeof metric?.total === "number" && metric.total > 0) {
    return (metric.covered / metric.total) * 100;
  }
  return 0;
}

function validateTotals(totals) {
  const deficits = [];
  for (const [metric, threshold] of Object.entries(THRESHOLDS)) {
    const pct = toPercent(totals[metric]);
    if (pct < threshold) {
      deficits.push({ metric, pct, threshold });
    }
  }
  return deficits;
}

function formatDeficit({ metric, pct, threshold }) {
  return `${metric} coverage ${pct.toFixed(2)}% is below the ${threshold.toFixed(2)}% policy`;
}

async function main() {
  const summary = await loadSummary();
  const totals = summary?.total;
  if (!totals) {
    console.error("Vitest coverage summary is missing total metrics.");
    process.exit(1);
  }

  const deficits = validateTotals(totals);
  if (deficits.length) {
    console.error("Vitest coverage policy violations detected:");
    for (const deficit of deficits) {
      console.error(` - ${formatDeficit(deficit)}`);
    }
    process.exit(1);
  }

  console.log("Vitest coverage thresholds satisfied.");
}

main().catch((error) => {
  if (!process.exitCode) {
    console.error(error);
    process.exit(1);
  }
});
