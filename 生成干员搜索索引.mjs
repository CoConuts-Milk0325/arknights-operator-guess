import { readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const root = fileURLToPath(new URL('./', import.meta.url));
const require = createRequire(import.meta.url);
const pronunciations = { 重岳: 'chong yue', 仇白: 'qiu bai' };

function normalize(value) {
  return value.normalize('NFKC').toLowerCase().replace(/[üǖǘǚǜ]/g, 'v')
    .normalize('NFD').replace(/\p{M}/gu, '').replace(/[^\p{L}\p{N}]/gu, '');
}

export async function generateOperatorSearchIndex() {
  // 使用语音项目已有的依赖；构建时在 npm ci 后调用，无需在线拼音服务。
  const { pinyin } = require('./voice-guess-arknights/node_modules/pinyin-pro');
  const table = await readFile(join(root, '明日方舟干员名字与外号对应表.md'), 'utf8');
  const aliasesByName = new Map();
  for (const line of table.split(/\r?\n/)) {
    if (!line.startsWith('|')) continue;
    const columns = line.split('|').slice(1, -1).map(value => value.trim());
    if (columns[0] === '名字' || /^:?-+:?$/.test(columns[0])) continue;
    if (columns.length !== 2 || !columns[0]) throw new Error(`外号表格式有误：${line}`);
    const key = normalize(columns[0]);
    const aliases = columns[1].split('、').map(value => value.trim())
      .filter(value => value && value !== '—' && normalize(value) !== key);
    aliasesByName.set(key, [...new Set([...(aliasesByName.get(key) || []), ...aliases])]);
  }

  const context = { window: {} };
  vm.runInNewContext(await readFile(join(root, '猜干员网页游戏', '事实索引.js'), 'utf8'), context);
  const voiceOperators = JSON.parse(await readFile(join(root, 'voice-guess-arknights', 'public', 'data', 'operators.json'), 'utf8'));
  const names = new Set([
    ...context.window.GUESS_DATA.operators.map(operator => operator.name),
    ...voiceOperators.map(operator => operator['干员']),
  ]);
  const index = {};
  for (const name of names) {
    const key = normalize(name);
    const aliases = aliasesByName.get(key) || [];
    const full = new Set();
    const initials = new Set();
    for (const text of [name, ...aliases]) {
      const override = pronunciations[text];
      full.add(normalize(override || pinyin(text, { toneType: 'none', v: true, type: 'array' }).join('')));
      initials.add(normalize(override
        ? override.split(' ').map(syllable => syllable[0]).join('')
        : pinyin(text, { pattern: 'first', toneType: 'none', v: true, type: 'array' }).join('')));
    }
    index[key] = { aliases, pinyinFull: [...full], pinyinInitials: [...initials] };
  }

  const serialized = JSON.stringify(index, null, 2);
  await writeFile(join(root, '猜干员网页游戏', '干员搜索索引.js'),
    `// 由最终外号表和游戏干员名册生成；运行 node 生成干员搜索索引.mjs 更新。\nwindow.OPERATOR_SEARCH_INDEX = ${serialized};\n`);
  await writeFile(join(root, 'voice-guess-arknights', 'src', 'operatorSearchIndex.json'), `${serialized}\n`);
  console.log(`干员搜索索引已生成：${Object.keys(index).length} 个名字，${Object.values(index).filter(entry => entry.aliases.length).length} 个名字有外号。`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  await generateOperatorSearchIndex();
}
