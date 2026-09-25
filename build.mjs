import { cp, mkdir, rm } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const output = join(root, 'dist');
const game = join(root, '猜干员网页游戏');
const archive = join(root, '干员档案展示版');
const archiveOutput = join(output, '干员档案展示版');

await rm(output, { recursive: true, force: true });
await mkdir(archiveOutput, { recursive: true });

for (const name of ['游戏样式.css', '游戏逻辑.js', '事实索引.js']) {
  await cp(join(game, name), join(output, name));
}
await cp(join(game, '首页.html'), join(output, 'index.html'));

for (const name of ['首页.html', '档案样式.css', '检索索引.js', '检索功能.js']) {
  await cp(join(archive, name), join(archiveOutput, name));
}
for (const name of ['干员档案', '非干员档案']) {
  await cp(join(archive, name), join(archiveOutput, name), { recursive: true });
}

console.log('Static site ready in dist/');
