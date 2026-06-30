/**
 * Build all 3 frontends in one command (public local or Vercel output).
 * Usage: node scripts/build-all-frontends.mjs [public|vercel]
 */
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(__dirname, '..');
const pathsFile = join(root, 'deploy', 'public_paths.json');

const DEFAULT_PATHS = {
  mentee: 'hskjchaihldkajj',
  mentor: 'hjgafjkshdgfahjkkjcsdhkk',
  superadmin: 'yaghkcjhaiuhahjks',
};

const APPS = [
  { role: 'mentee', folder: 'frontend', slugKey: 'mentee' },
  { role: 'mentor', folder: 'frontend-admin', slugKey: 'mentor' },
  { role: 'superadmin', folder: 'frontend-superadmin', slugKey: 'superadmin' },
];

const mode = (process.argv[2] || 'vercel').toLowerCase();
const isPublic = mode === 'public';
const outDir = join(root, 'deploy', isPublic ? 'public' : 'vercel-out');

function loadPaths() {
  if (!existsSync(pathsFile)) return DEFAULT_PATHS;
  try {
    const data = JSON.parse(readFileSync(pathsFile, 'utf8'));
    return {
      mentee: String(data.mentee || DEFAULT_PATHS.mentee).replace(/^\/|\/$/g, ''),
      mentor: String(data.mentor || DEFAULT_PATHS.mentor).replace(/^\/|\/$/g, ''),
      superadmin: String(data.superadmin || DEFAULT_PATHS.superadmin).replace(/^\/|\/$/g, ''),
    };
  } catch {
    return DEFAULT_PATHS;
  }
}

function run(cmd, cwd, env = {}) {
  execSync(cmd, {
    cwd,
    stdio: 'inherit',
    env: { ...process.env, ...env },
    shell: true,
  });
}

const paths = loadPaths();
const apiUrl = (process.env.VITE_API_URL || process.env.BACKEND_PUBLIC_URL || '').replace(/\/$/, '');

console.log('=== Phong Van — build all frontends ===');
console.log('Mode:', mode);
console.log('Output:', outDir);
if (apiUrl) console.log('VITE_API_URL:', apiUrl);
console.log('Paths:', paths);
console.log('');

run('node scripts/ensure-rollup-native.mjs', root);

if (existsSync(outDir)) rmSync(outDir, { recursive: true, force: true });
mkdirSync(outDir, { recursive: true });

if (!isPublic) {
  cpSync(join(root, 'deploy', 'landing', 'index.html'), join(outDir, 'index.html'));
} else {
  mkdirSync(join(outDir, 'mentee'), { recursive: true });
  mkdirSync(join(outDir, 'mentor'), { recursive: true });
  mkdirSync(join(outDir, 'superadmin'), { recursive: true });
}

for (const app of APPS) {
  const slug = paths[app.slugKey];
  const basePath = `/${slug}/`;
  const appDir = join(root, app.folder);

  console.log(`[build] ${app.role} → ${basePath}`);

  run('npm run build', appDir, {
    VITE_BASE_PATH: basePath,
    VITE_API_URL: apiUrl,
  });

  if (isPublic) {
    const roleFolder = app.role;
    cpSync(join(appDir, 'dist'), join(outDir, roleFolder), { recursive: true });
    const menteeSvg = join(root, 'frontend', 'public', 'tron-tru-girl.svg');
    if (app.role === 'mentee' && existsSync(menteeSvg)) {
      cpSync(menteeSvg, join(outDir, roleFolder, 'tron-tru-girl.svg'));
    }
  } else {
    cpSync(join(appDir, 'dist'), join(outDir, slug), { recursive: true });
    const menteeSvg = join(root, 'frontend', 'public', 'tron-tru-girl.svg');
    if (app.role === 'mentee' && existsSync(menteeSvg)) {
      cpSync(menteeSvg, join(outDir, slug, 'tron-tru-girl.svg'));
    }
  }
}

console.log('');
console.log('Build xong:', outDir);
