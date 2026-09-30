import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'

const REPORTS = 'D:/代码/配音猜干员/语音复核'
const ROOT = process.argv[2] || 'D:/代码/配音猜干员/语音文件'
const KEY = fs.readFileSync(path.join(process.cwd(), '.env.local'), 'utf8').match(/SILICONFLOW_API_KEY=(.+)/)[1].trim()
const ENDPOINT = 'https://api.siliconflow.cn/v1/audio/transcriptions'
const PRIMARY = 'Qwen/Qwen3-ASR-1.7B'
const FALLBACK = 'XingChenAGI/XingChenASR-V3.2-Ultra'
const CACHE = path.join(process.cwd(), '.bwiki-cache', 'asr-local')
const CONCURRENCY = 6

const list = fs.readFileSync(path.join(REPORTS, 'suspicious.tsv'), 'utf8').trim().split('\n').slice(1)
const rows = list.map(line => {
  const [name, language, category, seconds, chars, base, cps, ratio, file] = line.split('\t')
  return { name, language, category, seconds: Number(seconds), chars: Number(chars), base: Number(base), cps: Number(cps), ratio: Number(ratio), file }
})
console.log(`待听 ${rows.length} 条；先试 ${PRIMARY}，失败或额度不足回落 ${FALLBACK}`)

fs.mkdirSync(CACHE, { recursive: true })
const kana = text => /[぀-ゟ゠-ヿ]/.test(text)
const han = text => /[㐀-鿿]/.test(text)

async function listen(file) {
  const full = path.join(ROOT, file)
  const hash = crypto.createHash('sha1').update(full).digest('hex').slice(0, 16)
  const cacheFile = path.join(CACHE, `${hash}.json`)
  if (fs.existsSync(cacheFile)) return JSON.parse(fs.readFileSync(cacheFile, 'utf8'))
  const buffer = fs.readFileSync(full)
  for (const model of [PRIMARY, FALLBACK]) {
    try {
      const form = new FormData()
      form.append('file', new Blob([buffer], { type: 'audio/mpeg' }), path.basename(full).slice(0, 40) + '.mp3')
      form.append('model', model)
      const res = await fetch(ENDPOINT, { method: 'POST', headers: { Authorization: `Bearer ${KEY}` }, body: form, signal: AbortSignal.timeout(60000) })
      if (res.status === 402 || res.status === 429) { console.log(`  ${model} 额度/限流 ${res.status}，改用下一个模型`); continue }
      const payload = JSON.parse(await res.text())
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const record = { model, text: payload.text || '', lang: payload.language || '', billed: payload.usage?.seconds || 0, bytes: buffer.length }
      fs.writeFileSync(cacheFile, JSON.stringify(record))
      return record
    } catch (error) {
      if (model === FALLBACK) {
        const record = { model, text: '', lang: '', error: error.message, bytes: buffer.length }
        fs.writeFileSync(cacheFile, JSON.stringify(record))
        return record
      }
    }
  }
}

const results = []
let cursor = 0
async function worker() {
  while (cursor < rows.length) {
    const row = rows[cursor++]
    const heard = await listen(row.file)
    const text = (heard.text || '').replace(/\s/g, '')
    const verdict = heard.error ? `转写失败 ${heard.error}`
      : !text ? '空转写（疑似静音/坏文件）'
      : kana(text) && !han(text) ? '音频是日文，不是国语'
      : row.ratio > 3 ? '音频远短于台词，非本句完整朗读'
      : text.length < row.chars * 0.4 ? '音频内容与台词字数严重不符'
      : '音频是中文且与台词长度相符'
    results.push({ ...row, heard: text.slice(0, 60), verdict, model: heard.model, billed: heard.billed || 0 })
    if (results.length % 25 === 0) console.log(`  ${results.length}/${rows.length}`)
  }
}
await Promise.all(Array.from({ length: CONCURRENCY }, worker))

const counts = {}
for (const row of results) counts[row.verdict] = (counts[row.verdict] || 0) + 1
console.log(`\n判定分布：${JSON.stringify(counts, null, 0)}`)
console.log(`实际计费音频 ${results.reduce((n, r) => n + r.billed, 0)} 秒 ≈ ¥${(results.reduce((n, r) => n + r.billed, 0) * 0.00022).toFixed(2)}`)

const out = ['name\tlanguage\tcategory\tseconds\tchars\tcategoryBase\tcharsPerSecond\tratio\tverdict\theard']
for (const row of results.sort((a, b) => b.ratio - a.ratio).concat().sort((a, b) => (a.verdict.startsWith('音频是中文') ? 1 : 0) - (b.verdict.startsWith('音频是中文') ? 1 : 0))) {
  out.push([row.name, row.language, row.category, row.seconds, row.chars, row.base, row.cps.toFixed(1), row.ratio.toFixed(2), row.verdict, row.heard].join('\t'))
}
fs.writeFileSync(path.join(REPORTS, 'suspicious-listened.tsv'), out.join('\n') + '\n')
console.log(`明细已写出 ${path.join(REPORTS, 'suspicious-listened.tsv')}`)
for (const row of results.slice(0, 10)) console.log(`  ${(row.name + ' ' + row.category).padEnd(20)} ${row.seconds.toFixed(2)}s/${row.chars}字  ${row.verdict}  | ${row.heard.slice(0, 26)}`)
