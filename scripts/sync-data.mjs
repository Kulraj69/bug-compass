import { copyFile, mkdir } from 'node:fs/promises';
await mkdir(new URL('../public/', import.meta.url), { recursive: true });
for (const file of ['atlas.json', 'atlas.csv']) {
  await copyFile(new URL(`../data/${file}`, import.meta.url), new URL(`../public/${file}`, import.meta.url));
}
