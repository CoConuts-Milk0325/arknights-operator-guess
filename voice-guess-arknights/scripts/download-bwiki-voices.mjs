import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.join(__dirname, '..')
const VOICES = path.join(ROOT, 'public', 'data', 'voices')
const BASE = 'https://patchwiki.biligame.com/images/arknights/'
const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
  referer: 'https://wiki.biligame.com/arknights/',
}

const args = process.argv.slice(2)
const argAfter = name => (args.includes(name) ? args[args.indexOf(name) + 1] : null)
const OUT = path.resolve(argAfter('--out') || path.join(ROOT, '..', '语音文件'))
const LIMIT = Number(argAfter('--limit') || 0)
const CONCURRENCY = Number(argAfter('--concurrency') || 6)
const PACING = Number(argAfter('--pacing') || 700)
const HALT_AFTER = Number(argAfter('--halt-after') || 20)
const only = argAfter('--only')?.split(',')

let consecutiveFailures = 0
let halted = false

// Windows forbids \ / : * ? " < > | and control chars; dialogue also needs a length cap.
function safeName(text, hash) {
  const cleaned = String(text || '')
    .replace(/[\u0000-\u001f\\/:*?"<>|]/g, '、')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/[. ]+$/, '')
  const keep = cleaned.slice(0, 100) || '未标注'
  return `${keep}__${hash}`
}

function collect() {
  const jobs = []
  const seen = new Set()
  for (const file of fs.readdirSync(VOICES)) {
    const name = file.slice(0, -5)
    if (only && !only.includes(name)) continue
    const shard = JSON.parse(fs.readFileSync(path.join(VOICES, file), 'utf8'))
    for (const [language, categories] of Object.entries(shard)) {
      if (language !== '中文' && language !== '日文') continue
      for (const [category, entries] of Object.entries(categories)) {
        for (const entry of entries) {
          const url = typeof entry === 'string' ? entry : entry?.url
          if (!url?.startsWith('bwiki:')) continue
          const rel = url.slice('bwiki:'.length)
          const hash = path.basename(rel, '.mp3')
          jobs.push({
            name, language, category, rel,
            text: typeof entry === 'string' ? '' : entry?.text || '',
            target: path.join(OUT, name, language, `${safeName(entry?.text || category, hash)}.mp3`),
            url: BASE + rel,
          })
          seen.add(rel)
        }
      }
    }
  }
  return { jobs, unique: seen.size }
}

async function download(job) {
  if (fs.existsSync(job.target) && fs.statSync(job.target).size > 512) return { job, status: '已存在' }
  for (let attempt = 0; attempt < 4; attempt++) {
    try {
      const res = await fetch(job.url, { headers: HEADERS, signal: AbortSignal.timeout(60000) })
      if (res.status === 404) return { job, status: '404' }
      // 403/429/567 都是限速或风控信号，立刻上报为限流而不是继续重试
      if (res.status === 403 || res.status === 429 || res.status === 567) return { job, status: `限流 ${res.status}` }
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const buffer = Buffer.from(await res.arrayBuffer())
      if (buffer.length < 512) throw new Error('内容过小')
      fs.mkdirSync(path.dirname(job.target), { recursive: true })
      const tmp = `${job.target}.${process.pid}.part`
      fs.writeFileSync(tmp, buffer)
      fs.renameSync(tmp, job.target)
      return { job, status: 'ok', bytes: buffer.length }
    } catch (error) {
      if (attempt === 3) return { job, status: `失败 ${error.message}` }
      await new Promise(r => setTimeout(r, 1000 * 2 ** attempt))
    }
  }
}

async function main() {
  const { jobs, unique } = collect()
  const queue = LIMIT ? jobs.slice(0, LIMIT) : jobs
  console.log(`目标目录 ${OUT}`)
  console.log(`条目 ${jobs.length} 个（唯一文件 ${unique} 个），本次处理 ${queue.length}，并发 ${CONCURRENCY}`)
  fs.mkdirSync(OUT, { recursive: true })

  const counts = {}
  const failures = []
  let bytes = 0
  let cursor = 0
  let done = 0
  async function worker() {
    while (!halted && cursor < queue.length) {
      const result = await download(queue[cursor++])
      const bad = result.status === '404' || result.status.startsWith('限流') || result.status.startsWith('失败')
      if (bad) {
        consecutiveFailures++
        if (consecutiveFailures >= HALT_AFTER) {
          halted = true
          console.log(`连续 ${HALT_AFTER} 次失败，主动停止（重跑会跳过已下载的文件）`)
        }
      } else {
        consecutiveFailures = 0
      }
      const bucket = result.status.startsWith('限流') ? '限流' : result.status
      counts[bucket] = (counts[bucket] || 0) + 1
      if (result.bytes) bytes += result.bytes
      if (bad) failures.push(`${result.status}\t${result.job.url}\t${result.job.name}/${result.job.language}/${path.basename(result.job.target)}`)
      if (++done % 500 === 0) console.log(`  ${done}/${queue.length}  已下载 ${(bytes / 1024 / 1024).toFixed(0)}MB`)
      if (!halted && PACING) await new Promise(r => setTimeout(r, PACING))
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, worker))

  const manifest = ['operator\tlanguage\tcategory\ttext\tfile\turl']
  const oneLine = text => String(text || '').replace(/[\t\r\n]+/g, ' ')
  for (const job of jobs) manifest.push([job.name, job.language, job.category, oneLine(job.text), path.relative(OUT, job.target).replace(/\\/g, '/'), job.url].join('\t'))
  fs.writeFileSync(path.join(OUT, 'manifest.tsv'), manifest.join('\n') + '\n')
  if (failures.length) fs.writeFileSync(path.join(OUT, 'failures.tsv'), failures.join('\n') + '\n')

  console.log(`完成 ${done}：${JSON.stringify(counts)}，新下载 ${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`)
  if (failures.length) console.log(`异常 ${failures.length} 条见 failures.tsv`)
}

main()
