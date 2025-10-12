#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import { analyzeUi } from './analyze-ui.mjs';

const __dirname = path.dirname(new URL(import.meta.url).pathname);
const projectRoot = path.resolve(__dirname, '../../');
const configDir = path.join(projectRoot, 'config');
const baselinePath = path.join(configDir, 'ui-quality-baseline.json');

const metrics = await analyzeUi();

const INLINE_STYLE_THRESHOLD = 0;
const COMPONENT_DEFAULT_MAX = 400;

const inlineStyleAllowance = Object.fromEntries(
  Object.entries(metrics.inlineStyles.byFile)
    .filter(([, count]) => count > INLINE_STYLE_THRESHOLD)
    .sort(([a], [b]) => a.localeCompare(b))
);

const componentLineAllowance = {};
for (const [file, components] of Object.entries(metrics.components.byFile)) {
  const maxLines = Math.max(...components.map((component) => component.lines));
  if (maxLines > COMPONENT_DEFAULT_MAX) {
    componentLineAllowance[file] = maxLines;
  }
}

const baseline = {
  generatedAt: new Date().toISOString(),
  notes: 'Automatically generated baseline. Update after removing inline styles or breaking down components.',
  componentDefaultMax: COMPONENT_DEFAULT_MAX,
  inlineStyleAllowance,
  componentLineAllowance,
};

await fs.mkdir(configDir, { recursive: true });
await fs.writeFile(baselinePath, `${JSON.stringify(baseline, null, 2)}\n`, 'utf8');

console.log(`Updated baseline at ${path.relative(projectRoot, baselinePath)}`);
