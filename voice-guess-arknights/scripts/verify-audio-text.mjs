import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'

const REPORTS = 'D:/代码/配音猜干员/语音复核'
const ROOT = 'D:/代码/配音猜干员/语音文件'
const OUT = path.join(REPORTS, 'verified.jsonl')
const CACHE = path.join(process.cwd(), '.bwiki-cache', 'asr-local')
const args = process.argv.slice(2)
const argAfter = name => (args.includes(name) ? args[args.indexOf(name) + 1] : null)
const LANG = argAfter('--language') || '中文'
const MODEL = argAfter('--model') || 'XingChenAGI/XingChenASR-V3.2-Ultra'
const LIMIT = Number(argAfter('--limit') || 0)
const CONCURRENCY = Number(argAfter('--concurrency') || 10)
const KEY = fs.readFileSync(path.join(process.cwd(), '.env.local'), 'utf8').match(/SILICONFLOW_API_KEY=(.+)/)[1].trim()
const ENDPOINT = 'https://api.siliconflow.cn/v1/audio/transcriptions'

const norm = text => String(text || '').replace(/[^\p{L}\p{N}]/gu, '')
function dice(a, b) {
  if (!a || !b) return 0
  if (a === b) return 1
  const grams = s => { const m = new Map(); for (let i = 0; i < s.length - 1; i++) { const g = s.slice(i, i + 2); m.set(g, (m.get(g) || 0) + 1) } return m }
  const ga = grams(a), gb = grams(b)
  let overlap = 0
  for (const [g, n] of ga) overlap += Math.min(n, gb.get(g) || 0)
  return (2 * overlap) / (a.length - 1 + b.length - 1)
}

const rows = fs.readFileSync(path.join(ROOT, 'manifest.tsv'), 'utf8').trim().split('\n').slice(1)
  .map(line => {
    const [name, language, category, text, file, url] = line.split('\t')
    return { name, language, category, text, file, url }
  })
  .filter(row => row.language === LANG)

const done = new Set()
if (fs.existsSync(OUT)) {
  for (const line of fs.readFileSync(OUT, 'utf8').trim().split('\n')) {
    try { done.add(JSON.parse(line).file) } catch { /* skip a torn line */ }
  }
}
const queue = rows.filter(row => !done.has(row.file)).slice(0, LIMIT || Infinity)
console.log(`${LANG} 池共 ${rows.length} 条，已完成 ${done.size}，本次处理 ${queue.length}，model=${MODEL}，并发 ${CONCURRENCY}`)
if (!queue.length) process.exit(0)

fs.mkdirSync(CACHE, { recursive: true })
const stream = fs.createWriteStream(OUT, { flags: 'a' })
let heard = 0
let cursor = 0
const started = Date.now()

async function transcribe(file) {
  const hash = crypto.createHash('sha1').update(`${MODEL}|${file}`).digest('hex').slice(0, 16)
  const cacheFile = path.join(CACHE, `${hash}.json`)
  if (fs.existsSync(cacheFile)) return JSON.parse(fs.readFileSync(cacheFile, 'utf8'))
  const buffer = fs.readFileSync(path.join(ROOT, file))
  const form = new FormData()
  form.append('file', new Blob([buffer], { type: 'audio/mpeg' }), 'clip.mp3')
  form.append('model', MODEL)
  const res = await fetch(ENDPOINT, { method: 'POST', headers: { Authorization: `Bearer ${KEY}` }, body: form, signal: AbortSignal.timeout(60000) })
  const body = await res.text()
  if (!res.ok) throw new Error(`HTTP ${res.status} ${body.slice(0, 80)}`)
  const payload = JSON.parse(body)
  const record = { text: payload.text || '', language: payload.language || '' }
  fs.writeFileSync(cacheFile, JSON.stringify(record))
  return record
}

async function worker() {
  while (cursor < queue.length) {
    const row = queue[cursor++]
    let result
    try {
      const heardText = await transcribe(row.file)
      const score = dice(norm(heardText.text), norm(row.text))
      result = { ...row, model: MODEL, transcript: heardText.text, score, verdict: score >= 0.85 ? '吻合' : score >= 0.6 ? '近似' : score >= 0.3 ? '存疑' : score === 0 ? '空转写' : '不符' }
    } catch (error) {
      result = { ...row, model: MODEL, transcript: '', score: -1, verdict: `错误 ${error.message.slice(0, 60)}` }
    }
    stream.write(JSON.stringify(result) + '\n')
    heard++
    if (heard % 200 === 0) {
      const rate = heard / ((Date.now() - started) / 1000)
      console.log(`  ${heard}/${queue.length}  ${rate.toFixed(1)} 条/秒  预计剩余 ${((queue.length - heard) / rate / 60).toFixed(0)} 分钟`)
    }
  }
}
await Promise.all(Array.from({ length: CONCURRENCY }, worker))
stream.end()

const all = fs.readFileSync(OUT, 'utf8').trim().split('\n').map(line => JSON.parse(line)).filter(row => row.language === LANG)
const counts = {}
for (const row of all) counts[row.verdict] = (counts[row.verdict] || 0) + 1
console.log(`\n${LANG} 池判定：${JSON.stringify(counts, null, 0)}`)
const worst = all.filter(row => row.verdict === '不符' || row.verdict === '存疑').sort((a, b) => a.score - b.score)
for (const row of worst.slice(0, 15)) console.log(`  ${(row.name + ' ' + row.category).padEnd(20)} ${(row.score * 100).toFixed(0)}%  台词「${norm(row.text).slice(0, 16)}」听到「${norm(row.transcript).slice(0, 16)}」`)
console.log(`\n逐条结果在 ${OUT}`)
