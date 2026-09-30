import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.join(__dirname, '..')
const PAIRS_FILE = path.join(ROOT, '.bwiki-cache', 'pairs.json')
const CACHE_DIR = path.join(ROOT, '.bwiki-cache', 'durations')

const BWIKI_BASE = 'https://patchwiki.biligame.com/images/arknights/'
const PRTS_BASE = 'https://torappu.prts.wiki/assets/audio/'
const HEADERS = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36', referer: 'https://prts.wiki/' }

// PRTS WAV 头给的是绝对真值，但采样率与声道数必须从 fmt 块读，不能假定 44.1k 单声道
// （本仓库曾经这样假定，于是把娜仁图亚的一条 21 秒国语算成 23 秒，误判成"另一版录音"）。
const WAV_HEADER = 44

function wavSeconds(total, head) {
  const buffer = Buffer.from(head, 'base64')
  if (buffer.slice(0, 4).toString('latin1') !== 'RIFF' || buffer.slice(8, 12).toString('latin1') !== 'WAVE') return null
  const fmt = buffer.indexOf('fmt ')
  // tag(4) size(4) format(2) channels(2) rate(4) byteRate(4) —— byteRate 在标签后第 16 字节
  if (fmt < 0 || fmt + 20 > buffer.length) return null
  const bytesPerSecond = buffer.readUInt32LE(fmt + 16)
  if (!bytesPerSecond) return null
  const data = buffer.indexOf('data')
  const payload = data >= 0 && data + 8 <= buffer.length ? Math.min(buffer.readUInt32LE(data + 4), total - (data + 8)) : total - WAV_HEADER
  return payload / bytesPerSecond
}
const LAYER1 = [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448]
const LAYER3_1 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]
const LAYER3_2 = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]

/** One 64-byte Range request yields both the total size (content-range) and the first frame header. */
async function probe(url) {
  const file = path.join(CACHE_DIR, `${crypto.createHash('sha1').update(url).digest('hex').slice(0, 20)}.json`)
  if (fs.existsSync(file)) return JSON.parse(fs.readFileSync(file, 'utf8'))
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const res = await fetch(url, { headers: { ...HEADERS, Range: 'bytes=0-63' }, signal: AbortSignal.timeout(20000) })
      if (!res.ok && res.status !== 206) throw new Error(`HTTP ${res.status}`)
      const body = Buffer.from(await res.arrayBuffer())
      const total = Number((res.headers.get('content-range') || '').split('/')[1]) || Number(res.headers.get('content-length'))
      if (!total) throw new Error('拿不到总长度')
      const record = { total, head: body.toString('base64') }
      fs.writeFileSync(file, JSON.stringify(record))
      return record
    } catch (error) {
      if (attempt === 2) return { error: error.message }
      await new Promise(r => setTimeout(r, 500 * (attempt + 1)))
    }
  }
}

function mp3Bitrate(raw) {
  const buffer = Buffer.from(raw, 'base64')
  for (let offset = 0; offset + 4 <= buffer.length; offset++) {
    if (buffer[offset] !== 0xff || (buffer[offset + 1] & 0xe0) !== 0xe0) continue
    const header = buffer.readUInt32BE(offset)
    const versionBits = (header >>> 19) & 0x03
    const layerBits = (header >>> 17) & 0x03
    const bitrateIndex = (header >>> 12) & 0x0f
    const rateIndex = (header >>> 10) & 0x03
    if (versionBits === 1 || layerBits === 0 || bitrateIndex === 0 || bitrateIndex === 15 || rateIndex === 3) continue
    const mpeg1 = versionBits === 3
    const table = layerBits === 3 ? LAYER1 : mpeg1 ? LAYER3_1 : LAYER3_2
    const samples = layerBits === 3 ? 384 : layerBits === 2 ? 1152 : mpeg1 ? 1152 : 576
    const rate = [[44100, 48000, 32000], [24000, 16000, 22050], [11025, 12000, 8000]][mpeg1 ? 0 : versionBits === 2 ? 1 : 2][rateIndex]
    const bps = table[bitrateIndex] * 1000
    if (bps && rate) return { bps, frameSeconds: samples / rate }
  }
  return null
}

const args = process.argv.slice(2)
const argAfter = name => (args.includes(name) ? args[args.indexOf(name) + 1] : null)
const SAMPLE = Number(argAfter('--sample') || 2000)
const SEED = Number(argAfter('--seed') || 4242)
const DRIFT = argAfter('--drift')
const CATEGORY = argAfter('--category')
const NAMES = argAfter('--names')?.split(',')
const TOLERANCE = Number(argAfter('--tolerance') || 0.05)

const prtsWavUrl = pair => `${PRTS_BASE}${pair.prts.endsWith('.wav') ? pair.prts : `${pair.prts}.wav`}`

async function bwikiSeconds(url) {
  const meta = await probe(url)
  if (!meta.total) return { error: meta.error || '无数据' }
  const codec = mp3Bitrate(meta.head)
  if (!codec) return { error: '无法解析 MP3 头' }
  return { seconds: meta.total * 8 / codec.bps, bps: codec.bps }
}

async function prtsSeconds(url) {
  const meta = await probe(url)
  if (!meta.total) return { error: meta.error || '无数据' }
  const seconds = wavSeconds(meta.total, meta.head)
  return seconds ? { seconds } : { error: 'WAV 头无法解析' }
}

function pick(pairs) {
  let state = SEED >>> 0 || 1
  const random = () => ((state = (state * 1664525 + 1013904223) >>> 0) / 4294967296)
  const scoped = NAMES ? pairs.filter(pair => NAMES.includes(pair.name)) : pairs
  const base = DRIFT ? scoped.filter(pair => pair.drift === DRIFT) : CATEGORY ? scoped.filter(pair => pair.category === CATEGORY) : scoped
  const list = base.slice()
  const taken = []
  while (list.length && taken.length < SAMPLE) taken.push(list.splice(Math.floor(random() * list.length), 1)[0])
  return taken
}

async function main() {
  fs.mkdirSync(CACHE_DIR, { recursive: true })
  const pairs = pick(JSON.parse(fs.readFileSync(PAIRS_FILE, 'utf8')))
  console.log(`时长比对 ${pairs.length} 对（HEAD only，容差 ${(TOLERANCE * 100).toFixed(0)}%）`)

  const rows = []
  let cursor = 0
  async function worker() {
    while (cursor < pairs.length) {
      const pair = pairs[cursor++]
      const [b, p] = [await bwikiSeconds(BWIKI_BASE + pair.bwiki), await prtsSeconds(prtsWavUrl(pair))]
      if (!b.seconds || !p.seconds) {
        rows.push({ pair, status: '取长失败', detail: b.error || p.error })
        continue
      }
      const delta = Math.abs(b.seconds - p.seconds)
      const slack = Math.max(0.3, Math.max(b.seconds, p.seconds) * TOLERANCE)
      const same = delta <= slack
      // When the two hosts disagree, the stored 台词 says which one holds this language's take:
      // Mandarin speech runs ~4.5 characters per second, so a mismatching estimate means the
      // other host is carrying a different language or an older recording.
      const chars = String(pair.text || '').replace(/[^\p{L}\p{N}]/gu, '').length
      const estimate = chars / 4.5
      const closer = same || chars < 10 ? null : Math.abs(b.seconds - estimate) < Math.abs(p.seconds - estimate) ? 'bwiki' : 'prts'
      rows.push({ pair, status: same ? '同长' : '差异', closer, delta: Math.round(delta * 1000) / 1000, chars, need: Math.round(estimate * 100) / 100, bw: Math.round(b.seconds * 1000) / 1000, prts: Math.round(p.seconds * 1000) / 1000, bps: b.bps })
      if (rows.length % 250 === 0) console.log(`  ${rows.length}/${pairs.length}`)
    }
  }
  await Promise.all(Array.from({ length: 10 }, worker))

  const poolOf = row => (row.pair.prts.startsWith('voice_custom') ? '方言' : row.pair.language === '日文' ? '日文' : '中文')
  const tally = {}
  for (const row of rows) tally[`${poolOf(row)}/${row.status}`] = (tally[`${poolOf(row)}/${row.status}`] || 0) + 1
  for (const [key, value] of Object.entries(tally).sort()) console.log(`  ${key}: ${value}`)

  const edges = [0.05, 0.1, 0.2, 0.3, 0.5, 1, 2, 5]
  const hist = {}
  for (const row of rows.filter(r => r.delta !== undefined)) {
    const bucket = edges.find(edge => row.delta <= edge) ?? '>5'
    hist[bucket] = (hist[bucket] || 0) + 1
  }
  console.log(`|Δ| 分布: ${JSON.stringify(hist)}`)
  const closer = {}
  for (const row of rows.filter(r => r.status === '差异')) closer[row.closer || '台本太短无法裁定'] = (closer[row.closer || '台本太短无法裁定'] || 0) + 1
  if (Object.keys(closer).length) console.log(`台本字数裁定: ${JSON.stringify(closer)}`)

  const diff = rows.filter(row => row.status === '差异')
  if (diff.length) {
    console.log(`\n时长不符 ${diff.length} 条 (${(diff.length / rows.length * 100).toFixed(1)}%):`)
    for (const row of diff.slice(0, 25)) console.log(`  ${row.pair.name} ${row.pair.category}#${row.pair.index} bwiki=${row.bw}s prts=${row.prts}s Δ${row.delta}s`)
  }
  const reportPath = path.join(ROOT, '.bwiki-cache', 'duration-report.json')
  const merged = new Map()
  if (fs.existsSync(reportPath)) for (const row of JSON.parse(fs.readFileSync(reportPath, 'utf8'))) merged.set([row.pair.name, row.pair.language, row.pair.category, row.pair.index].join('|'), row)
  for (const row of rows) merged.set([row.pair.name, row.pair.language, row.pair.category, row.pair.index].join('|'), row)
  fs.writeFileSync(reportPath, JSON.stringify([...merged.values()], null, 1))
  console.log(`累计证据条目 ${merged.size} 对`)
}

main()
