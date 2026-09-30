import { cp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { generateRulePage } from './猜干员网页游戏/生成规则页.mjs';
import { generateOperatorSearchIndex } from './生成干员搜索索引.mjs';

const root = dirname(fileURLToPath(import.meta.url));
const output = join(root, 'dist');
const game = join(root, '猜干员网页游戏');
const voice = join(root, 'voice-guess-arknights');
const archive = join(root, '干员档案展示版');

try {
  await readFile(join(voice, 'package.json'));
} catch {
  throw new Error('语音游戏子模块未初始化，请先运行 git submodule update --init --recursive');
}

const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm';
execFileSync(npm, ['ci'], { cwd: voice, stdio: 'inherit', shell: process.platform === 'win32' });
await generateOperatorSearchIndex();
execFileSync(npm, ['run', 'build', '--', '--base=/voice/'], { cwd: voice, stdio: 'inherit', shell: process.platform === 'win32' });

await rm(output, { recursive: true, force: true });
await mkdir(join(output, 'clues'), { recursive: true });
await mkdir(join(output, '干员档案展示版'), { recursive: true });

await cp(join(root, 'portal', 'index.html'), join(output, 'index.html'));
await cp(join(root, 'portal', 'style.css'), join(output, 'style.css'));
await cp(join(root, 'portal', 'assets'), join(output, 'assets'), { recursive: true });

await generateRulePage(game);
for (const name of ['游戏样式.css', '游戏逻辑.js', '事实索引.js', '干员搜索索引.js', '规则说明.css', '规则说明.html', '机制核对记录.md', '事实索引与游戏数据修改报告.md']) {
  await cp(join(game, name), join(output, 'clues', name));
}
const clueHtml = (await readFile(join(game, '首页.html'), 'utf8'))
  .replace('<head>', '<head>\n  <base href="/clues/">');
await writeFile(join(output, 'clues', 'index.html'), clueHtml);
await writeFile(join(output, 'clues', '首页.html'), clueHtml);

await cp(join(voice, 'dist'), join(output, 'voice'), { recursive: true });
const voiceIndex = join(output, 'voice', 'index.html');
await writeFile(voiceIndex, (await readFile(voiceIndex, 'utf8'))
  .replace('<head>', '<head>\n  <base href="/voice/">'));

const archiveOutput = join(output, '干员档案展示版');
for (const name of ['首页.html', '档案样式.css', '检索索引.js', '检索功能.js', '使用说明.md']) {
  await cp(join(archive, name), join(archiveOutput, name));
}
for (const name of ['干员档案', '非干员档案']) {
  await cp(join(archive, name), join(archiveOutput, name), { recursive: true });
}

await writeFile(join(output, '首页.html'), '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=/clues/"><title>正在前往猜干员</title></head><body><a href="/clues/">前往猜干员</a></body></html>');
console.log('双游戏站点已生成至 dist/');
