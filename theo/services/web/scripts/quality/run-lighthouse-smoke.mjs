#!/usr/bin/env node
import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';

const __dirname = path.dirname(new URL(import.meta.url).pathname);
const projectRoot = path.resolve(__dirname, '../../');
const repoRoot = path.resolve(projectRoot, '../../..');
const appOrigin = process.env.APP_ORIGIN ?? 'http://127.0.0.1:3000';

function run(command, args, options = {}) {
  return new Promise((resolve, reject) => {
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
        reject(new Error(`${command} ${args.join(' ')} exited with code ${code}`));
      }
    });
  });
}

async function waitForServer(url, timeoutMs = 30_000) {
  const start = Date.now();
  const controller = new AbortController();
  const { signal } = controller;
  async function attempt() {
    try {
      const response = await fetch(url, { method: 'GET', signal });
      if (response.ok) {
        return;
      }
    } catch (error) {
      // retry
    }
    if (Date.now() - start > timeoutMs) {
      throw new Error(`Timed out waiting for ${url}`);
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
    return attempt();
  }
  return attempt();
}

async function runLighthouse() {
  await run('npm', ['run', 'build'], { cwd: projectRoot, env: { ...process.env, NEXT_TELEMETRY_DISABLED: '1', NEXT_DISABLE_TELEMETRY: '1' } });

  const server = spawn('npm', ['run', 'start', '--', '--hostname', '127.0.0.1', '--port', '3000'], {
    cwd: projectRoot,
    env: {
      ...process.env,
      NEXT_TELEMETRY_DISABLED: '1',
      NEXT_DISABLE_TELEMETRY: '1',
    },
    stdio: ['ignore', 'inherit', 'inherit'],
  });

  try {
    await waitForServer(appOrigin);
    const lhciBinary = path.join(projectRoot, 'node_modules', '.bin', 'lhci');
    try {
      await fs.access(lhciBinary);
    } catch (error) {
      throw new Error('lhci CLI not installed. Did you run npm install?');
    }

    await run(lhciBinary, ['autorun', '--config', path.relative(projectRoot, path.join(repoRoot, 'lighthouserc.json'))], {
      cwd: projectRoot,
      env: {
        ...process.env,
        APP_ORIGIN: appOrigin,
        LHCI_COLLECT__URL: appOrigin,
        LHCI_COLLECT__START_SERVER_COMMAND: '',
        LHCI_COLLECT__START_SERVER_READY_TIMEOUT: '60000',
      },
    });
  } finally {
    server.kill('SIGTERM');
  }
}

runLighthouse().catch((error) => {
  console.error(error.message ?? error);
  process.exit(1);
});
