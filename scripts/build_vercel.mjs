import { cpSync, existsSync, rmSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const result = spawnSync(npm, ['--prefix', 'frontend', 'run', 'build'], {
  cwd: root,
  env: {
    ...process.env,
    // The Vercel deployment hosts the API on the same origin. Clear any stale
    // dashboard-level value left over from the retired Render service.
    VITE_API_URL: '',
  },
  shell: process.platform === 'win32',
  stdio: 'inherit',
});

if (result.status !== 0) {
  process.exit(result.status ?? 1);
}

const source = resolve(root, 'frontend', 'dist');
const destination = resolve(root, 'public');
if (!existsSync(source)) {
  throw new Error(`Vite did not create the expected output directory: ${source}`);
}

rmSync(destination, { recursive: true, force: true });
cpSync(source, destination, { recursive: true });
console.log(`Copied the production dashboard to ${destination}`);
