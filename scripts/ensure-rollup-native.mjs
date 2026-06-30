/**
 * Ensure platform-specific Rollup native binary is installed.
 * Fixes npm optional-deps bug: https://github.com/npm/cli/issues/4828
 */
import { execSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(join(root, 'package.json'));

const ROLLUP_VERSION = '4.62.2';

function nativePackages() {
  const { platform, arch } = process;

  if (platform === 'linux') {
    return [
      `@rollup/rollup-linux-${arch}-gnu`,
      `@rollup/rollup-linux-${arch}-musl`,
    ];
  }
  if (platform === 'darwin') {
    return [`@rollup/rollup-darwin-${arch}`];
  }
  if (platform === 'win32') {
    if (arch === 'ia32') return ['@rollup/rollup-win32-ia32-msvc'];
    return [
      `@rollup/rollup-win32-${arch}-msvc`,
      `@rollup/rollup-win32-${arch}-gnu`,
    ];
  }
  return [];
}

function isInstalled(pkg) {
  try {
    require.resolve(pkg);
    return true;
  } catch {
    return false;
  }
}

function install(pkg) {
  console.log(`[rollup] Installing missing native package: ${pkg}`);
  execSync(`npm install ${pkg}@${ROLLUP_VERSION} --no-save --force`, {
    cwd: root,
    stdio: 'inherit',
    shell: true,
  });
}

const packages = nativePackages();
if (!packages.length) {
  process.exit(0);
}

let installedAny = false;
for (const pkg of packages) {
  if (!isInstalled(pkg)) {
    try {
      install(pkg);
      installedAny = true;
    } catch (error) {
      console.warn(`[rollup] Could not install ${pkg}:`, error.message);
    }
  }
}

if (installedAny) {
  const primary = packages[0];
  if (!isInstalled(primary)) {
    console.error(`[rollup] Still missing required package: ${primary}`);
    process.exit(1);
  }
}

console.log(`[rollup] Native binary ready on ${process.platform}-${process.arch}`);
