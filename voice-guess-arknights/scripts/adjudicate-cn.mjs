import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'

const REPORTS = 'D:/代码/配音猜干员/语音复核'
const ROOT = 'D:/代码/配音猜干员/语音文件'
const VERIFIED = path.join(REPORTS, 'verified.jsonl')
const OUT = path.join(REPORTS, 'cn-adjudication.tsv')
const CACHE = path.join(process.cwd(), '.bwiki-cache', 'asr-local')
const MODEL = 'Qwen/Qwen3-ASR-1.7B'
const KEY = fs.readFileSync(path.join(process.cwd(), '.env.local'), 'utf8').match(/SILICONFLOW_API_KEY=(.+)/)[1].trim()
const args = process.argv.slice(2)
const argAfter = (name, dflt) => (args.includes(name) ? args[args.indexOf(name) + 1] : dflt)
const CONCURRENCY = Number(argAfter('--concurrency', '5'))
const LIMIT = Number(argAfter('--limit', '0'))

const norm = text => String(text || '').replace(/[\s]*(提升信赖至\d+%以查看|提升至精英阶段\d以查看)/g, '').replace(/&#160;/g, ' ').replace(/[^\p{L}\p{N}]/gu, '')
function dice(a, b) {
  if (!a || !b) return 0
  if (a === b) return 1
  const grams = s => { const m = new Map(); for (let i = 0; i < s.length - 1; i++) { const g = s.slice(i, i + 2); m.set(g, (m.get(g) || 0) + 1) } return m }
  const ga = grams(a), gb = grams(b)
  let overlap = 0
  for (const [g, n] of ga) overlap += Math.min(n, gb.get(g) || 0)
  return (2 * overlap) / (a.length - 1 + b.length - 1)
}

// Every 台词 of the same operator, so a clip that is really another line gets named, not just flagged.
const pool = new Map()
const VOICES = path.join(process.cwd(), 'public', 'data', 'voices')
for (const file of fs.readdirSync(VOICES)) {
  const name = file.slice(0, -5)
  const shard = JSON.parse(fs.readFileSync(path.join(VOICES, file), 'utf8'))
  const list = []
  for (const [language, categories] of Object.entries(shard)) {
    if (language !== '中文' && language !== '日文') continue
    for (const [category, entries] of Object.entries(categories)) {
      entries.forEach((entry, index) => list.push({
        language, category, index,
        text: typeof entry === 'string' ? '' : entry.text || '',
        url: typeof entry === 'string' ? entry : entry.url,
      }))
    }
  }
  pool.set(name, list)
}

const seen = new Set()
const targets = []
for (const line of fs.readFileSync(VERIFIED, 'utf8').trim().split('\n')) {
  let row
  try { row = JSON.parse(line) } catch { continue }
  if (!['不符', '存疑', '空转写'].includes(row.verdict) && !String(row.verdict).startsWith('错误')) continue
  if (seen.has(row.file)) continue
  seen.add(row.file)
  targets.push(row)
}
if (LIMIT) targets.length = LIMIT
console.log(`待复核 ${targets.length} 条（XingChen 判定为 不符/存疑/空转写/错误），model=${MODEL}`)

async function transcribe(file) {
  const hash = crypto.createHash('sha1').update(`${MODEL}|${file}`).digest('hex').slice(0, 16)
  const cacheFile = path.join(CACHE, `${hash}.json`)
  if (fs.existsSync(cacheFile)) return JSON.parse(fs.readFileSync(cacheFile, 'utf8'))
  const buffer = fs.readFileSync(path.join(ROOT, file))
  const form = new FormData()
  form.append('file', new Blob([buffer], { type: 'audio/mpeg' }), 'clip.mp3')
  form.append('model', MODEL)
  const res = await fetch('https://api.siliconflow.cn/v1/audio/transcriptions', {
    method: 'POST', headers: { Authorization: `Bearer ${KEY}` }, body: form, signal: AbortSignal.timeout(60000)
  })
  const body = await res.text()
  if (!res.ok) throw new Error(`${res.status} ${body.slice(0, 50)}`)
  const payload = JSON.parse(body)
  const record = { text: payload.text || '', language: payload.language || '', seconds: payload.usage?.seconds ?? null }
  fs.writeFileSync(cacheFile, JSON.stringify(record))
  return record
}

const results = []
let billed = 0, cursor = 0, done = 0
async function worker() {
  while (cursor < targets.length) {
    const row = targets[cursor++]
    try {
      const heard = await transcribe(row.file)
      billed += heard.seconds || 0
      const mine = norm(row.text)
      const said = norm(heard.text)
      const own = dice(mine, said)
      const candidates = (pool.get(row.name) || [])
        .map(slot => ({ slot, score: dice(norm(slot.text), said) }))
        .sort((a, b) => b.score - a.score)
      const best = candidates.find(item => item.score >= 0.6)
      const sameSlot = best && best.slot.language === row.language && best.slot.category === row.category && best.slot.text === row.text
      const verdict = own >= 0.6 ? '已澄清（同一句）'
        : !said && !heard.text ? '无人声（转写为空）'
        : heard.language && heard.language !== 'Chinese' ? `语种为 ${heard.language}`
        : best && !sameSlot && best.score >= 0.75 ? `台词错位：更像 ${best.slot.language}/${best.slot.category}#${best.slot.index}`
        : best && best.score > own + 0.2 ? `更像 ${best.slot.language}/${best.slot.category}#${best.slot.index}（${best.score.toFixed(2)}）`
        : '仍不符'
      results.push({ ...row, heard: heard.text, language: heard.language, own: own.toFixed(2), best: best ? `${best.slot.language}/${best.slot.category}#${best.slot.index} ${best.score.toFixed(2)}` : '', verdict })
    } catch (error) {
      results.push({ ...row, heard: '', language: '', own: '-1', best: '', verdict: `错误 ${error.message.slice(0, 40)}` })
    }
    if (++done % 100 === 0) console.log(`  ${done}/${targets.length} 已计费 ${billed}s ≈ ¥${(billed * 0.00022).toFixed(2)}`)
  }
}
await Promise.all(Array.from({ length: CONCURRENCY }, worker))

const counts = {}
for (const row of results) counts[row.verdict] = (counts[row.verdict] || 0) + 1
console.log(`\n复核判定：${JSON.stringify(counts, null, 0)}`)
const header = ['verdict', 'operator', 'language', 'category', 'text', 'heard', 'language_heard', 'dice_own', 'best_other', 'url']
const body = [header.join('\t'), ...results
  .sort((a, b) => a.verdict.localeCompare(b.verdict))
  .map(row => [row.verdict, row.name, row.language, row.category, row.text.replace(/\s+/g, ' '), String(row.heard).replace(/\s+/g, ' ').slice(0, 60), row.language, row.own, row.best, row.url].join('\t'))]
fs.writeFileSync(OUT, body.join('\n') + '\n')
console.log(`明细写出 ${OUT}（${results.length} 条），计费 ${billed} 秒 ≈ ¥${(billed * 0.00022).toFixed(2)}`)
for (const row of results.filter(r => r.verdict.startsWith('台词错位')).slice(0, 20)) console.log(`  ${row.name} ${row.language}/${row.category}#${row.text.slice(0, 12)} 听到「${row.heard.slice(0, 22)}」`)
