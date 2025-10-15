#!/usr/bin/env node
/**
 * Initializes Lighthouse CI baseline by running audits on critical pages
 * and storing results for future comparisons.
 * 
 * Usage:
 *   node scripts/lighthouse-init-baseline.mjs
 * 
 * Prerequisites:
 *   - Next.js dev/prod server running at APP_ORIGIN (default: http://127.0.0.1:3000)
 *   - @lhci/cli installed in theo/services/web
 */

import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '..');
const webRoot = path.join(repoRoot, 'theo', 'services', 'web');
const baselineDir = path.join(repoRoot, '.lighthouseci', 'baseline');
const appOrigin = process.env.APP_ORIGIN ?? 'http://127.0.0.1:3000';

function run(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    console.log(`▶ ${command} ${args.join(' ')}`);
    const child = spawn(command, args, {
      stdio: 'inherit',
      shell: false,
      ...options,
    });
    child.on('error', reject);
    child.on('exit', (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`${command} exited with code ${code}`));
      }
    });
  });
}

async function checkServer() {
  console.log(`\n🔍 Checking if server is running at ${appOrigin}...`);
  try {
    const response = await fetch(appOrigin, { method: 'HEAD', signal: AbortSignal.timeout(5000) });
    if (response.ok) {
      console.log('✓ Server is running\n');
      return true;
    }
  } catch (error) {
    console.error(`✗ Server not reachable at ${appOrigin}`);
    console.error('  Start the server with: cd theo/services/web && npm run dev');
    console.error('  Or build + start: npm run build && npm run start\n');
    return false;
  }
  return false;
}

async function runLighthouseBaseline() {
  console.log('🚀 Initializing Lighthouse CI baseline\n');
  
  // Ensure baseline directory exists
  await fs.mkdir(baselineDir, { recursive: true });

  // Run Lighthouse CI
  const lhciPath = path.join(webRoot, 'node_modules', '.bin', 'lhci');
  const configPath = path.join(repoRoot, 'lighthouserc.json');

  try {
    await run(lhciPath, ['autorun', '--config', configPath], {
      cwd: webRoot,
      env: {
        ...process.env,
        LHCI_COLLECT__URL: JSON.stringify([
          `${appOrigin}`,
          `${appOrigin}/verse/John.3.16`,
          `${appOrigin}/search`,
        ]),
        LHCI_COLLECT__START_SERVER_COMMAND: '',
      },
    });
  } catch (error) {
    console.error('\n✗ Lighthouse CI failed:', error.message);
    throw error;
  }

  // Move results to baseline directory
  const currentDir = path.join(webRoot, '.lighthouseci');
  const manifestSrc = path.join(currentDir, 'manifest.json');
  const manifestDest = path.join(baselineDir, 'manifest.json');

  try {
    await fs.access(manifestSrc);
    await fs.copyFile(manifestSrc, manifestDest);
    console.log(`\n✓ Baseline saved to ${baselineDir}/manifest.json`);
    
    // Copy full reports too
    const files = await fs.readdir(currentDir);
    for (const file of files) {
      if (file.startsWith('lhr-') && file.endsWith('.json')) {
        const src = path.join(currentDir, file);
        const dest = path.join(baselineDir, file);
        await fs.copyFile(src, dest);
      }
    }
    
    console.log('✓ Full reports copied to baseline directory');
  } catch (error) {
    console.error('\n✗ Failed to save baseline:', error.message);
    throw error;
  }

  console.log('\n✅ Baseline initialization complete!');
  console.log('   Future CI runs will compare against these scores.');
}

async function main() {
  const serverReady = await checkServer();
  if (!serverReady) {
    process.exit(1);
  }

  try {
    await runLighthouseBaseline();
  } catch (error) {
    console.error('\n❌ Baseline initialization failed\n');
    process.exit(1);
  }
}

main();
