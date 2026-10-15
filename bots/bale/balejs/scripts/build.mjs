import { mkdir, copyFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const out = resolve(root, 'dist');
await mkdir(out, { recursive: true });
await copyFile(resolve(root, 'src/runtime.mjs'), resolve(out, 'index.js'));
await copyFile(resolve(root, 'src/index.d.ts'), resolve(out, 'index.d.ts'));
console.log('balejs: copied ESM runtime + TypeScript declarations to dist/ (Node 18+; no external runtime deps)');
