#!/usr/bin/env node
import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import { analyzeUi } from './analyze-ui.mjs';

const __dirname = path.dirname(new URL(import.meta.url).pathname);
const projectRoot = path.resolve(__dirname, '../../');
const repoRoot = path.resolve(projectRoot, '../../..');
const outputDir = path.join(repoRoot, 'docs', 'dashboards');
const outputPath = path.join(outputDir, 'ui-quality-dashboard.md');
const baselinePath = path.join(projectRoot, 'config', 'ui-quality-baseline.json');

function run(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: projectRoot,
      env: { ...process.env, NEXT_TELEMETRY_DISABLED: '1', NEXT_DISABLE_TELEMETRY: '1' },
      stdio: 'pipe',
      ...options,
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => {
      stdout += chunk;
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk;
    });
    child.on('error', reject);
    child.on('exit', (code) => {
      if (code === 0) {
        resolve({ stdout, stderr });
      } else {
        reject(new Error(`${command} ${args.join(' ')} failed with code ${code}\n${stderr}`));
      }
    });
  });
}

async function readCoverageSummary() {
  const summaryPath = path.join(projectRoot, 'coverage', 'coverage-summary.json');
  try {
    const data = await fs.readFile(summaryPath, 'utf8');
    return JSON.parse(data);
  } catch (error) {
    return null;
  }
}

async function collectBundleMetrics() {
  try {
    const result = await run('npm', ['run', 'build']);
    const match = result.stdout.match(/First Load JS shared by all\s+([0-9.,]+)\s*kB/i);
    const bundleKb = match ? parseFloat(match[1].replace(/,/g, '')) : null;
    return { bundleKb, raw: result.stdout };
  } catch (error) {
    return { bundleKb: null, raw: String(error) };
  }
}

async function main() {
  const [metrics, baseline] = await Promise.all([
    analyzeUi(),
    fs.readFile(baselinePath, 'utf8').then(JSON.parse),
  ]);

  const coverageSummary = await readCoverageSummary();
  const totalInlineBaseline = Object.values(baseline.inlineStyleAllowance).reduce((sum, value) => sum + value, 0);
  const inlineDelta = metrics.inlineStyles.total - totalInlineBaseline;
  const inlineLeaders = Object.entries(metrics.inlineStyles.byFile)
    .filter(([, count]) => count > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10);

  const bundleMetrics = await collectBundleMetrics();

  const coverageSection = coverageSummary
    ? (() => {
        const totals = coverageSummary.total;
        return [
          `- Statements: ${(totals.statements.pct ?? 0).toFixed(2)}%`,
          `- Branches: ${(totals.branches.pct ?? 0).toFixed(2)}%`,
          `- Functions: ${(totals.functions.pct ?? 0).toFixed(2)}%`,
          `- Lines: ${(totals.lines.pct ?? 0).toFixed(2)}%`,
        ].join('\n');
      })()
    : '- Coverage summary not found. Run `npm run test:vitest` to refresh metrics.';

  const largestComponents = metrics.components.largest.slice(0, 10).map((entry) => {
    const limit = baseline.componentLineAllowance[entry.file] ?? baseline.componentDefaultMax;
    const delta = entry.lines - limit;
    const trend = delta > 0 ? `(+${delta})` : `(${delta})`;
    return `| ${entry.name} | ${entry.file} | ${entry.lines} | ${limit} | ${trend} |`;
  });

  const inlineTable = inlineLeaders.map(([file, count]) => {
    const limit = baseline.inlineStyleAllowance[file] ?? 0;
    const delta = count - limit;
    const trend = delta > 0 ? `+${delta}` : `${delta}`;
    return `| ${file} | ${count} | ${limit} | ${trend} |`;
  });

  const markdown = `# Web UI Quality Dashboard\n\n` +
    `Generated: ${new Date().toISOString()}\n\n` +
    `## Inline Styles\n\n` +
    `- Current total: ${metrics.inlineStyles.total} (baseline ${totalInlineBaseline}, delta ${inlineDelta >= 0 ? '+' : ''}${inlineDelta})\n` +
    `- Top files by inline styles:\n\n` +
    `| File | Count | Baseline | Δ |\n| --- | ---: | ---: | ---: |\n` +
    `${inlineTable.join('\n')}\n\n` +
    `## Component Size\n\n` +
    `| Component | File | Lines | Limit | Δ |\n| --- | --- | ---: | ---: | ---: |\n` +
    `${largestComponents.join('\n')}\n\n` +
    `## Test Coverage\n\n${coverageSection}\n\n` +
    `## Bundle Size\n\n` +
    (bundleMetrics.bundleKb
      ? `- First Load JS shared by all: ${bundleMetrics.bundleKb.toFixed(2)} kB\n`
      : `- Unable to parse bundle size from build output.\n`) +
    `- Build summary stored in \`docs/dashboards/.latest-build.log\` for detailed inspection.\n`;

  await fs.mkdir(outputDir, { recursive: true });
  await fs.writeFile(outputPath, `${markdown}\n`, 'utf8');
  await fs.writeFile(path.join(outputDir, '.latest-build.log'), bundleMetrics.raw, 'utf8');

  console.log(`Dashboard written to ${path.relative(repoRoot, outputPath)}`);
}

main().catch((error) => {
  console.error(error.message ?? error);
  process.exit(1);
});
