import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'

const REPORTS = 'D:/代码/配音猜干员/语音复核'
const ROOT = 'D:/代码/配音猜干员/语音文件'
const CACHE = path.join(process.cwd(), '.bwiki-cache', 'asr-local')
const MODEL = 'Qwen/Qwen3-ASR-1.7B'
const KEY = fs.readFileSync(path.join(process.cwd(), '.env.local'), 'utf8').match(/SILICONFLOW_API_KEY=(.+)/)[1].trim()

const args = process.argv.slice(2)
const perOperator = Number(args[args.indexOf('--per') + 1] || 3)

const lines = fs.readFileSync(path.join(REPORTS, 'column-tag-mismatch.tsv'), 'utf8').trim().split('\n').slice(1)
const rows = lines.map(line => {
  const [name, language, category, text, tags, url] = line.split('\t')
  return { name, language, category, text, tags, url }
})

const grouped = new Map()
for (const row of rows) (grouped.get(row.name) || grouped.set(row.name, []).get(row.name)).push(row)

const queue = []
for (const [name, list] of grouped) {
  const step = Math.max(1, Math.floor(list.length / perOperator))
  for (let i = 0; i < list.length && queue.filter(q => q.name === name).length < perOperator; i += step) queue.push(list[i])
}
console.log(`${grouped.size} 名干员，抽查 ${queue.length} 条，model=${MODEL}`)

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
  if (!res.ok) throw new Error(`${res.status} ${body.slice(0, 80)}`)
  const payload = JSON.parse(body)
  const record = { text: payload.text || '', language: payload.language || '', seconds: payload.usage?.seconds ?? null }
  fs.writeFileSync(cacheFile, JSON.stringify(record))
  return record
}

// manifest maps url -> local file, so the sample is read from disk instead of re-downloaded
const manifest = fs.readFileSync(path.join(ROOT, 'manifest.tsv'), 'utf8').trim().split('\n').slice(1)
const fileByUrl = new Map(manifest.map(line => { const p = line.split('\t'); return [p[5], p[4]] }))

let billed = 0
let cursor = 0
async function worker() {
  while (cursor < queue.length) {
    const row = queue[cursor++]
    const file = fileByUrl.get(row.url)
    if (!file) { console.log(`  本地缺失 ${row.name} ${row.category}`); continue }
    try {
      const heard = await transcribe(file)
      billed += heard.seconds || 0
      console.log(`  ${row.name.padEnd(10)} ${row.language} ${row.category.padEnd(8)} => ${heard.language.padEnd(10)} ${heard.text.slice(0, 28)}`)
    } catch (error) {
      console.log(`  ${row.name} ${row.category} 失败 ${error.message}`)
    }
  }
}
await Promise.all(Array.from({ length: 4 }, worker))
console.log(`\n计费音频 ${billed} 秒 ≈ ¥${(billed * 0.00022).toFixed(2)}`)
