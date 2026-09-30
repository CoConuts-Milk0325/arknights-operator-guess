import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'

const REPORTS = 'D:/代码/配音猜干员/语音复核'
const ROOT = 'D:/代码/配音猜干员/语音文件'
const OUT = path.join(REPORTS, 'jp-language.jsonl')
const CACHE = path.join(process.cwd(), '.bwiki-cache', 'asr-local')
const args = process.argv.slice(2)
const argAfter = (name, dflt) => (args.includes(name) ? args[args.indexOf(name) + 1] : dflt)
const LANGUAGE = argAfter('--language', '日文')
const PER = Number(argAfter('--per', 2))
const MODEL = argAfter('--model', 'Qwen/Qwen3-ASR-1.7B')
const CONCURRENCY = Number(argAfter('--concurrency', '6'))
const KEY = fs.readFileSync(path.join(process.cwd(), '.env.local'), 'utf8').match(/SILICONFLOW_API_KEY=(.+)/)[1].trim()
const CATEGORIES = (argAfter('--categories', '') || '').split(',').filter(Boolean)
const NAMES = (argAfter('--names', '') || '').split(',').filter(Boolean)

const rows = fs.readFileSync(path.join(ROOT, 'manifest.tsv'), 'utf8').trim().split('\n').slice(1)
  .map(line => { const [name, language, category, text, file, url] = line.split('\t'); return { name, language, category, text, file, url } })
  .filter(row => row.language === LANGUAGE && (!CATEGORIES.length || CATEGORIES.includes(row.category)) && (!NAMES.length || NAMES.includes(row.name)))

// Spread the sample across each operator's category list so a partial-page mistake still shows up.
const byOperator = new Map()
for (const row of rows) (byOperator.get(row.name) || byOperator.set(row.name, []).get(row.name)).push(row)
const queue = []
for (const [, list] of byOperator) {
  const step = Math.max(1, Math.floor(list.length / PER))
  for (let i = 0, taken = 0; i < list.length && taken < PER; i += step, taken++) queue.push(list[i])
}

const done = new Set()
if (fs.existsSync(OUT)) for (const line of fs.readFileSync(OUT, 'utf8').trim().split('\n')) { try { done.add(JSON.parse(line).file) } catch { /* torn line */ } }
const todo = queue.filter(row => !done.has(row.file))
console.log(`${LANGUAGE} 池 ${rows.length} 条，抽样 ${queue.length} 条（${byOperator.size} 名干员 × ${PER}），已完成 ${done.size}，本次 ${todo.length}，model=${MODEL}`)
if (!todo.length) process.exit(0)

const stream = fs.createWriteStream(OUT, { flags: 'a' })
let billed = 0, cursor = 0, finished = 0
const started = Date.now()

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
  if (!res.ok) throw new Error(`${res.status} ${body.slice(0, 60)}`)
  const payload = JSON.parse(body)
  const record = { text: payload.text || '', language: payload.language || '', seconds: payload.usage?.seconds ?? null }
  fs.writeFileSync(cacheFile, JSON.stringify(record))
  return record
}

async function worker() {
  while (cursor < todo.length) {
    const row = todo[cursor++]
    try {
      const heard = await transcribe(row.file)
      billed += heard.seconds || 0
      stream.write(JSON.stringify({ ...row, heard: heard.text, language: heard.language, seconds: heard.seconds }) + '\n')
    } catch (error) {
      stream.write(JSON.stringify({ ...row, heard: '', language: `错误 ${error.message.slice(0, 40)}` }) + '\n')
    }
    if (++finished % 100 === 0) {
      const rate = finished / ((Date.now() - started) / 1000)
      console.log(`  ${finished}/${todo.length} ${rate.toFixed(1)} 条/秒 预计剩余 ${((todo.length - finished) / rate / 60).toFixed(0)} 分钟 已计费 ${billed}s ≈ ¥${(billed * 0.00022).toFixed(2)}`)
    }
  }
}
await Promise.all(Array.from({ length: Math.max(1, CONCURRENCY) }, worker))
stream.end()

const all = fs.readFileSync(OUT, 'utf8').trim().split('\n').map(line => { try { return JSON.parse(line) } catch { return null } }).filter(Boolean)
const counts = {}
for (const row of all) counts[row.language] = (counts[row.language] || 0) + 1
console.log(`\n语种分布：${JSON.stringify(counts, null, 0)}`)
const wrong = all.filter(row => row.language && row.language !== 'Japanese' && !row.language.startsWith('错误'))
console.log(`非日语 ${wrong.length} 条：`)
for (const row of wrong.slice(0, 40)) console.log(`  ${row.name.padEnd(12)} ${row.category.padEnd(8)} ${String(row.language).padEnd(9)}「${row.heard.slice(0, 26)}」`)
console.log(`合计计费 ${billed} 秒 ≈ ¥${(billed * 0.00022).toFixed(2)}`)
