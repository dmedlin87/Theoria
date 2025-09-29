import fs from 'node:fs';
import path from 'node:path';

const [baselineArg, currentArg] = process.argv.slice(2);

const baselinePath = baselineArg ?? path.join('.lighthouseci', 'baseline', 'manifest.json');
const currentPath = currentArg ?? path.join('.lighthouseci', 'current', 'manifest.json');

const readManifest = (manifestPath) => {
  if (!fs.existsSync(manifestPath)) {
    return null;
  }
  const raw = fs.readFileSync(manifestPath, 'utf8');
  try {
    return JSON.parse(raw);
  } catch (error) {
    console.warn(`Unable to parse ${manifestPath}:`, error.message);
    return null;
  }
};

const toEntries = (manifest) => {
  if (!manifest) return [];
  if (Array.isArray(manifest)) return manifest;
  if (Array.isArray(manifest.results)) return manifest.results;
  if (Array.isArray(manifest.runs)) return manifest.runs;
  if (Array.isArray(manifest.runWarnings)) {
    return manifest.runWarnings;
  }
  return [];
};

const toSummaryMap = (manifest) => {
  const entries = toEntries(manifest);
  return new Map(
    entries
      .filter((entry) => entry && entry.url)
      .map((entry) => [entry.url, entry.summary ?? entry?.scores ?? {}])
  );
};

const baselineManifest = readManifest(baselinePath);
if (!baselineManifest) {
  console.log('No baseline manifest found; skipping baseline comparison.');
  process.exit(0);
}

const currentManifest = readManifest(currentPath);
if (!currentManifest) {
  console.warn('Current manifest missing; unable to compare against baseline.');
  process.exit(0);
}

const baselineSummary = toSummaryMap(baselineManifest);
const currentSummary = toSummaryMap(currentManifest);

if (!baselineSummary.size || !currentSummary.size) {
  console.log('Baseline or current summary is empty; skipping comparison.');
  process.exit(0);
}

const trackedCategories = [
  ['performance', 'Performance'],
  ['accessibility', 'Accessibility'],
  ['best-practices', 'Best Practices'],
  ['seo', 'SEO']
];

for (const [url, currentScores] of currentSummary.entries()) {
  const baselineScores = baselineSummary.get(url);
  if (!baselineScores) {
    console.log(`No baseline scores stored for ${url}; skipping.`);
    continue;
  }

  console.log(`\nLighthouse comparison for ${url}`);
  for (const [key, label] of trackedCategories) {
    const before = baselineScores[key];
    const after = currentScores[key];
    if (typeof before !== 'number' || typeof after !== 'number') {
      console.log(`  ${label}: missing score data, skipping.`);
      continue;
    }
    const delta = (after - before) * 100;
    const formattedBefore = (before * 100).toFixed(1);
    const formattedAfter = (after * 100).toFixed(1);
    const prefix = delta === 0 ? '  ' : delta > 0 ? '  ↑' : '  ↓';
    console.log(
      `${prefix} ${label}: ${formattedAfter} (baseline ${formattedBefore}, delta ${delta.toFixed(1)})`
    );
  }
}
