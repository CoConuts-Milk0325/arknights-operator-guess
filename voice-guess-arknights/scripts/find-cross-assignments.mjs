import fs from 'node:fs'
import path from 'node:path'

// bwiki has been caught pasting one operator's file into another operator's language cell
// (红隼 got 翎羽's, 蓝毒's 选中2 repeats 白面鸮's, 远山's 中 cells hold 赫默's lines).
// Byte hashing only finds it when both pages list the file, so instead: take every clip the
// ASR pass could not match to its own 台词 and look for the closest 台词 in the whole corpus.
const REPORTS = 'D:/代码/配音猜干员/语音复核'
const ROOT = 'D:/代码/配音猜干员/语音文件'
const VOICES = path.join(process.cwd(), 'public', 'data', 'voices')
const MIN_SCORE = Number(process.argv[2] || 0.72)

const norm = text => String(text || '')
  .replace(/\s*(提升信赖至\d+%以查看|提升至精英阶段\d以查看)/g, '')
  .replace(/[^\p{L}\p{N}]/gu, '')
function dice(a, b) {
  if (!a || !b) return 0
  if (a === b) return 1
  const grams = s => { const m = new Map(); for (let i = 0; i < s.length - 1; i++) { const g = s.slice(i, i + 2); m.set(g, (m.get(g) || 0) + 1) } return m }
  const ga = grams(a), gb = grams(b)
  let overlap = 0
  for (const [g, n] of ga) overlap += Math.min(n, gb.get(g) || 0)
  return (2 * overlap) / (a.length - 1 + b.length - 1)
}

const corpus = []
for (const file of fs.readdirSync(VOICES)) {
  const name = file.slice(0, -5)
  const shard = JSON.parse(fs.readFileSync(path.join(VOICES, file), 'utf8'))
  for (const [language, categories] of Object.entries(shard)) {
    if (language !== '中文' && language !== '日文') continue
    for (const [category, entries] of Object.entries(categories)) {
      entries.forEach((entry, index) => {
        const text = typeof entry === 'string' ? '' : entry.text || ''
        if (norm(text).length >= 6) corpus.push({ name, language, category, index, key: norm(text) })
      })
    }
  }
}
console.log(`台本库 ${corpus.length} 条（>=6 字）`)

const rows = fs.readFileSync(path.join(REPORTS, 'cn-adjudication.tsv'), 'utf8').trim().split('\n').slice(1)
  .map(line => line.split('\t'))
  .filter(p => p[0] === '仍不符' || p[0].startsWith('台词错位'))

const hits = []
for (const p of rows) {
  const [verdict, name, language, category, text, heard] = p
  const key = norm(heard)
  if (key.length < 6) continue
  let best = null
  for (const item of corpus) {
    const score = dice(item.key, key)
    if (score >= MIN_SCORE && (!best || score > best.score)) best = { ...item, score }
  }
  if (!best) continue
  if (best.name === name) continue
  hits.push({ verdict, name, language, category, text, heard, best })
}

hits.sort((a, b) => b.best.score - a.best.score)
console.log(`\n听到的是别的干员的台词：${hits.length} 条`)
for (const h of hits) console.log(`  ${h.name.padEnd(10)} ${h.language}/${h.category.padEnd(6)} 台词「${h.text.slice(0, 16)}」\n     听到「${h.heard.slice(0, 24)}」= ${h.best.name}/${h.best.language}/${h.best.category}#${h.best.index} (${h.best.score.toFixed(2)})`)
const affected = new Map()
for (const h of hits) affected.set(h.name, (affected.get(h.name) || 0) + 1)
console.log(`\n涉及的干员：${[...affected].map(([k, v]) => `${k}(${v})`).join(' ')}`)
