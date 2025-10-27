#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import { analyzeUi } from './analyze-ui.mjs';

const __dirname = path.dirname(new URL(import.meta.url).pathname);
const projectRoot = path.resolve(__dirname, '../../');
const baselinePath = path.join(projectRoot, 'config', 'ui-quality-baseline.json');

async function loadBaseline() {
  try {
    const data = await fs.readFile(baselinePath, 'utf8');
    return JSON.parse(data);
  } catch (error) {
    throw new Error(`Unable to read baseline at ${path.relative(projectRoot, baselinePath)}. Run "npm run quality:baseline" first.`);
  }
}

function formatDelta(current, limit) {
  const delta = current - limit;
  return delta > 0 ? `+${delta}` : `${delta}`;
}

const baseline = await loadBaseline();
const metrics = await analyzeUi();

const inlineFailures = [];
for (const [file, count] of Object.entries(metrics.inlineStyles.byFile)) {
  const limit = baseline.inlineStyleAllowance[file] ?? 0;
  if (count > limit) {
    inlineFailures.push({ file, count, limit });
  }
}

const componentFailures = [];
for (const [file, components] of Object.entries(metrics.components.byFile)) {
  const maxLines = Math.max(...components.map((component) => component.lines));
  const limit = baseline.componentLineAllowance[file] ?? baseline.componentDefaultMax;
  if (maxLines > limit) {
    const offender = components.reduce((max, component) => (component.lines > max.lines ? component : max), components[0]);
    componentFailures.push({ file, component: offender.name, lines: maxLines, limit });
  }
}

if (inlineFailures.length === 0 && componentFailures.length === 0) {
  console.log('✅ UI quality gates satisfied.');
  const totalInlineLimit = Object.values(baseline.inlineStyleAllowance).reduce((sum, value) => sum + value, 0);
  const inlineDelta = formatDelta(metrics.inlineStyles.total, totalInlineLimit);
  console.log(`   Inline styles: ${metrics.inlineStyles.total} (${inlineDelta} vs baseline)`);
  console.log('   Largest components:');
  for (const entry of metrics.components.largest.slice(0, 5)) {
    const limit = baseline.componentLineAllowance[entry.file] ?? baseline.componentDefaultMax;
    const delta = formatDelta(entry.lines, limit);
    console.log(`     • ${entry.name} (${entry.file}) — ${entry.lines} lines (${delta})`);
  }
  process.exit(0);
}

console.error('❌ UI quality gates failed.');
if (inlineFailures.length > 0) {
  console.error('\nInline style regressions:');
  for (const failure of inlineFailures.sort((a, b) => b.count - a.count)) {
    const delta = formatDelta(failure.count, failure.limit);
    console.error(` - ${failure.file}: ${failure.count} inline styles (${delta} vs limit ${failure.limit})`);
  }
}

if (componentFailures.length > 0) {
  console.error('\nComponent size regressions:');
  for (const failure of componentFailures.sort((a, b) => b.lines - a.lines)) {
    const delta = formatDelta(failure.lines, failure.limit);
    console.error(` - ${failure.component} (${failure.file}): ${failure.lines} lines (${delta} vs limit ${failure.limit})`);
  }
}

process.exit(1);
