import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.join(__dirname, '..')
const PAIRS_FILE = path.join(ROOT, '.bwiki-cache', 'pairs.json')
const ASR_DIR = path.join(ROOT, '.bwiki-cache', 'asr')

const BWIKI_BASE = 'https://patchwiki.biligame.com/images/arknights/'
const PRTS_BASE = 'https://torappu.prts.wiki/assets/audio/'
const ENDPOINT = process.env.ASR_ENDPOINT || 'https://api.siliconflow.cn/v1/audio/transcriptions'
// XingChenASR returns junk for Japanese clips, so it is only a quota fallback, never the primary.
const MODELS = [process.env.ASR_MODEL || 'Qwen/Qwen3-ASR-1.7B', process.env.ASR_FALLBACK || 'XingChenAGI/XingChenASR-V3.2-Ultra'].filter((model, index, list) => model && list.indexOf(model) === index)
const MODEL = MODELS[0]
const CONCURRENCY = Number(process.env.ASR_CONCURRENCY || 8)

const args = process.argv.slice(2)
const argAfter = name => (args.includes(name) ? args[args.indexOf(name) + 1] : null)
const num = (name, value) => (argAfter(name) ? Number(argAfter(name)) : value)
const SAMPLE = num('--sample', 60)
const SEED = num('--seed', 20260923)
const DRIFT = argAfter('--drift')
const NAMES = argAfter('--names')?.split(',')
const PAIRS_IN = argAfter('--pairs') || PAIRS_FILE
const VERBOSE = args.includes('--verbose')

function apiKey() {
  if (process.env.SILICONFLOW_API_KEY) return process.env.SILICONFLOW_API_KEY.trim()
  const envFile = path.join(ROOT, '.env.local')
  if (fs.existsSync(envFile)) {
    const line = fs.readFileSync(envFile, 'utf8').split(/\r?\n/).find(l => /^\s*SILICONFLOW_API_KEY\s*=/.test(l))
    if (line) return line.split('=').slice(1).join('=').trim().replace(/^["']|["']$/g, '')
  }
  throw new Error('缺少 SILICONFLOW_API_KEY：设为环境变量，或写进 .env.local（已被 .gitignore 忽略）')
}

const sleep = ms => new Promise(r => setTimeout(r, ms))
const key = (...parts) => crypto.createHash('sha1').update(parts.join('|')).digest('hex').slice(0, 20)

// SenseVoice wraps output in <|zh|><|EMO|> style tags; strip those plus leading word-boundary marks.
function clean(text) {
  return String(text || '')
    .replace(/<\|[^|]*\|>/g, '')
    .replace(/[▁\s]/g, '')
    .replace(/[\p{P}\p{S}]/gu, '')
    .trim()
}

async function download(url, headers, attempt = 0) {
  try {
    const res = await fetch(url, { headers, signal: AbortSignal.timeout(30000) })
    if (!res.ok) return null
    const buffer = Buffer.from(await res.arrayBuffer())
    return buffer.length > 1024 ? buffer : null
  } catch (error) {
    if (attempt < 2) {
      await sleep(1500 * (attempt + 1))
      return download(url, headers, attempt + 1)
    }
    return null
  }
}

async function fetchClip(pair, source) {
  const browser = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36' }
  if (source === 'bwiki') return download(BWIKI_BASE + pair.bwiki, browser)
  const mp3 = (pair.prts.endsWith('.wav') ? pair.prts.slice(0, -4) : pair.prts).replace(/\.mp3$/, '') + '.mp3'
  const asMp3 = await download(PRTS_BASE + mp3, { ...browser, referer: 'https://prts.wiki/' })
  if (asMp3) return asMp3
  return download(PRTS_BASE + pair.prts, { ...browser, referer: 'https://prts.wiki/' })
}

async function transcribe(buffer, name, urlKey) {
  for (const model of MODELS) {
    const file = path.join(ASR_DIR, `${key(model, urlKey)}.json`)
    if (fs.existsSync(file)) return JSON.parse(fs.readFileSync(file, 'utf8'))
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const form = new FormData()
        form.append('file', new Blob([buffer], { type: 'audio/mpeg' }), name)
        form.append('model', model)
        const res = await fetch(ENDPOINT, { method: 'POST', headers: { Authorization: `Bearer ${apiKey()}` }, body: form, signal: AbortSignal.timeout(60000) })
        const body = await res.text()
        if (res.status === 429 || res.status === 402) { console.log(`  ${model} 配额/限流 ${res.status}，换下一个模型`); break }
        if (!res.ok) throw new Error(`HTTP ${res.status}: ${body.slice(0, 120)}`)
        const payload = JSON.parse(body)
        const seconds = payload.usage?.seconds || payload.duration || 0
        const text = payload.text || ''
        // XingChenASR once answered a 3s Japanese clip with a single 「我」: never let that count as evidence.
        if (text.replace(/[^\p{L}\p{N}]/gu, '').length < Math.max(1, seconds * 1.5)) throw new Error(`转写疑似失败: "${text}" / ${seconds}s`)
        const record = { text, model, seconds }
        fs.writeFileSync(file, JSON.stringify(record))
        await sleep(80)
        return record
      } catch (error) {
        if (attempt === 1) { console.log(`  ${model} 放弃: ${error.message}`); break }
        await sleep(600 * (attempt + 1))
      }
    }
  }
  throw new Error(`所有 ASR 模型均未产出可信转写（${MODELS.join(', ')}）`)
}

function poolOf(pair) {
  if (pair.prts.startsWith('voice_custom/')) return '方言'
  if (pair.language === '日文') return '日文'
  return '中文'
}

function sample(pairs) {
  let state = SEED >>> 0 || 1
  const random = () => ((state = (state * 1664525 + 1013904223) >>> 0) / 4294967296)
  const byPool = {}
  for (const pair of pairs) (byPool[poolOf(pair)] ||= []).push(pair)
  const picked = []
  const pools = Object.keys(byPool)
  for (const pool of pools) {
    const list = byPool[pool].slice()
    const take = Math.max(1, Math.round(SAMPLE / pools.length))
    for (let i = 0; i < take && list.length; i++) picked.push(list.splice(Math.floor(random() * list.length), 1)[0])
  }
  return picked
}

async function main() {
  fs.mkdirSync(ASR_DIR, { recursive: true })
  const pairs = JSON.parse(fs.readFileSync(PAIRS_IN, 'utf8'))
  let queue
  if (NAMES) {
    // Spread the quota: a few Mandarin-pool clips per named operator answers "is bwiki's （中） really Chinese".
    const per = Math.max(1, Math.ceil(SAMPLE / NAMES.length))
    queue = NAMES.flatMap(name => pairs.filter(pair => pair.name === name && pair.language === '中文' && !pair.category.includes('皮肤')).slice(0, per))
  } else if (DRIFT) {
    queue = pairs.filter(pair => pair.drift === DRIFT)
  } else {
    queue = sample(pairs)
  }
  const reportPath = NAMES ? 'asr-report-names.json' : 'asr-report.json'
  console.log(`配对表 ${pairs.length} 条，本次比对 ${queue.length} 条${NAMES ? `（指定 ${NAMES.length} 个干员的中文池）` : DRIFT ? `（drift=${DRIFT}）` : '（分层抽样）'}，model=${MODEL}`)

  const rows = []
  let cursor = 0
  async function worker() {
    while (cursor < queue.length) {
      const pair = queue[cursor++]
      try {
        const [bw, prts] = [await fetchClip(pair, 'bwiki'), await fetchClip(pair, 'prts')]
        if (!bw || !prts) {
          rows.push({ pair, status: '下载失败', bw: !!bw, prts: !!prts })
          continue
        }
        const [a, b] = [await transcribe(bw, 'a.mp3', pair.bwiki), await transcribe(prts, 'b.mp3', pair.prts)]
        const heardBwiki = clean(a.text)
        const heardPrts = clean(b.text)
        const says = (heard, script) => {
          const h = clean(heard)
          const s = clean(script)
          if (!h || !s) return null
          return h === s || h.includes(s.slice(0, 8)) || s.includes(h.slice(0, 8))
        }
        rows.push({
          pair,
          status: heardBwiki && heardBwiki === heardPrts ? '一致' : '不一致',
          bw: heardBwiki,
          prts: heardPrts,
          saysOurs: says(a.text, pair.text),
          saysTheirs: says(a.text, pair.bwikiText),
          prtsMatchesOwnScript: says(b.text, pair.text),
        })
      } catch (error) {
        rows.push({ pair, status: `错误 ${error.message}` })
      }
      if (rows.length % 10 === 0) console.log(`  ${rows.length}/${queue.length}`)
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, worker))

  const tally = {}
  for (const row of rows) {
    const pool = poolOf(row.pair)
    tally[pool] ||= { 一致: 0, 不一致: 0, 失败: 0 }
    if (row.status === '一致') tally[pool].一致++
    else if (row.status === '不一致') tally[pool].不一致++
    else tally[pool].失败++
  }
  for (const [pool, counts] of Object.entries(tally)) console.log(`${pool}: 一致 ${counts.一致} / 不一致 ${counts.不一致} / 失败 ${counts.失败}`)

  const bad = rows.filter(row => row.status !== '一致')
  if (bad.length) {
    console.log(`\n需要看的 ${bad.length} 条:`)
    for (const row of bad.slice(0, VERBOSE ? 999 : 15)) {
      console.log(`  [${row.status}] ${row.pair.name} ${row.pair.language} ${row.pair.category}#${row.pair.index}`)
      if (row.bw || row.prts) console.log(`     bwiki: ${row.bw}\n     prts : ${row.prts}\n     台词 : ${row.pair.text.slice(0, 40)}`)
    }
  } else console.log('\n抽样全部一致。')
  fs.writeFileSync(path.join(ROOT, '.bwiki-cache', reportPath), JSON.stringify(rows, null, 1))
}

main().catch(error => {
  console.error('音频比对失败:', error.message)
  process.exitCode = 1
})
