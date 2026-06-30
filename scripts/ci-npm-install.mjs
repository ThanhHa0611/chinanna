/**
 * Clean install for Linux CI (Vercel / Render static build).
 */
import { execSync } from 'node:child_process';
import { existsSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

function run(cmd) {
  console.log(`> ${cmd}`);
  execSync(cmd, { cwd: root, stdio: 'inherit', shell: true });
}

const dirs = [
  'node_modules',
  'frontend/node_modules',
  'frontend-admin/node_modules',
  'frontend-superadmin/node_modules',
];

for (const dir of dirs) {
  const path = join(root, dir);
  if (existsSync(path)) {
    rmSync(path, { recursive: true, force: true });
  }
}

run('npm install --include=optional');
run('node scripts/ensure-rollup-native.mjs');
